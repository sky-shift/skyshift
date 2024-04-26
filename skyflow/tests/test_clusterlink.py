"""
Unit tests for the Clusterlink APIs

Prerequisites : KIND (https://kind.sigs.k8s.io)

Run : pytest clusterlink_test.py
"""
import logging
import os
import subprocess
import sys
import time

import pytest

sys.path.append('path')

from skyflow.cluster_manager import KubernetesManager
from skyflow.network.cluster_linkv2 import (create_link, delete_export_service,
                                            delete_import_service,
                                            export_service, import_service,
                                            launch_clusterlink)

CL1 = "peer1"
CL2 = "peer2"
CL1NAME = "kind-" + CL1
CL2NAME = "kind-" + CL2

HTTPIMAGE = "hashicorp/http-echo"
HTTP_SERVER = "http-server"
DSTPORT = 8080


def _cleanup_clusters():

    def _delete_cluster(name):
        """ Deletes a KIND Cluster """
        os.system(f"kind delete cluster --name={name}")

    """ Cleans up test environment """
    _delete_cluster(CL1)
    _delete_cluster(CL2)


def _setup_clusters():
    """ Sets up KIND Cluster for test environment """

    def _create_cluster(name):
        """ Creates a KIND Cluster """
        os.system(f"kind create cluster  --name={name}")

    _create_cluster(CL1)
    time.sleep(1)
    _create_cluster(CL2)
    time.sleep(1)


def _load_services():
    """ Loads the services in clusters to be used for connectivity tests """
    os.system(f"kubectl config use-context {CL2NAME}")
    os.system(
        f"kubectl run http-server --image {HTTPIMAGE}"
        " --port 8080 -l app=http-server -- -listen=:8080 -text=clusterlink-hello"
    )
    os.system("kubectl wait --for=condition=Ready pod/http-server")
    os.system("kubectl create service nodeport http-server --tcp=8080:8080")


def _try_connection():
    """ Tries connecting to iperf3 server from the iperf3 client """
    logging.debug("Starting to test connection")
    os.system(f"kubectl config use-context {CL1NAME}")
    try:
        os.system("kubectl wait --for=condition=Ready pod/gwctl")
        direct_output = subprocess.check_output(
            f"kubectl exec -i gwctl -- timeout 30 sh -c "
            f"'until wget -T 1 http-server-{CL2NAME}:{DSTPORT} -q -O -; do sleep 0.1; done'",
            shell=True)

        logging.debug(f"{direct_output.decode()}")
        if "clusterlink-hello" in direct_output.decode():
            logging.debug("Successful connection")
            return True
    except subprocess.CalledProcessError as e:
        return False
    return False


def _delete_clusterlink_deployment():
    subprocess.getoutput(
        f"kubectl delete deployment cl-controlplane --context {CL1NAME}")
    subprocess.getoutput(
        f"kubectl delete deployment cl-controlplane --context {CL2NAME}")


def _wait():
    time.sleep(1)
    subprocess.getoutput(
        f"kubectl exec -i gwctl --context {CL1NAME} -- timeout 30 sh -c"
        " 'until timeout 1 nc -z http-server-{CL2NAME} {DSTPORT}; do sleep 0.1; done'"
    )


@pytest.mark.skip(reason="Broken and (probably) difficult to fix")
def test_clusterlink():
    """Tests connectivity using clusterlink APIs in KIND environment"""
    _cleanup_clusters()
    _setup_clusters()
    cluster1_manager = KubernetesManager(CL1NAME)
    cluster2_manager = KubernetesManager(CL2NAME)

    # Test Setup of Clusterlink on a fresh kubernetes cluster
    assert launch_clusterlink(cluster1_manager) is True
    assert launch_clusterlink(cluster2_manager) is True
    assert create_link(cluster1_manager, cluster2_manager) is True
    _load_services()
    assert export_service(HTTP_SERVER, cluster2_manager, [DSTPORT]) is True
    assert import_service(HTTP_SERVER, cluster1_manager,
                          cluster2_manager.cluster_name, [DSTPORT]) is True
    _wait()
    assert _try_connection() is True

    logging.debug("Starting re-export/import connection test")
    # Test deletion and export/import again
    assert delete_export_service(HTTP_SERVER, cluster2_manager) is True
    assert delete_import_service(HTTP_SERVER, cluster1_manager,
                                 cluster2_manager.cluster_name) is True
    time.sleep(1)
    assert export_service(HTTP_SERVER, cluster2_manager, [DSTPORT]) is True
    assert import_service(HTTP_SERVER, cluster1_manager,
                          cluster2_manager.cluster_name, [DSTPORT]) is True
    _wait()
    assert _try_connection() is True

    logging.debug("Starting deployment reset connection test")
    # Test destroying clusterlink deployment, and re-install
    _delete_clusterlink_deployment()
    assert launch_clusterlink(cluster1_manager) is True
    assert launch_clusterlink(cluster2_manager) is True
    _wait()
    assert _try_connection() is True
    _cleanup_clusters()
