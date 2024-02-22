"""
Unit tests for the Clusterlink APIs

Prerequisites : KIND (https://kind.sigs.k8s.io)

Run : pytest clusterlink_test.py
"""
import os
import subprocess
import sys
import time

import pytest

sys.path.append('path')

from skyflow.cluster_manager import KubernetesManager
from skyflow.network.cluster_linkv2 import (CL_DIRECTORY, create_link,
                                            export_service, import_service,
                                            launch_clusterlink)

cl1 = "peer1"
cl2 = "peer2"
cl1Name = "kind-" + cl1
cl2Name = "kind-" + cl2

test_service = "mlabbe/iperf3"
cluster1_service = "iperf3-client"
cluster2_service = "iperf3-server"
destPort = 5000


def delete_cluster(name):
    """ Deletes a KIND Cluster """
    os.system(f"kind delete cluster --name={name}")


def cleanup_clusters():
    """ Cleans up test environment """
    delete_cluster(cl1)
    delete_cluster(cl2)


def create_cluster(name):
    """ Creates a KIND Cluster """
    os.system(f"kind create cluster  --name={name}")


def setup_clusters():
    """ Sets up KIND Cluster for test environment """
    create_cluster(cl1)
    time.sleep(1)
    create_cluster(cl2)
    time.sleep(1)


def load_services():
    """ Loads the services in clusters to be used for connectivity tests """
    os.system(f"kubectl config use-context {cl1Name}")
    os.system(f"kubectl run iperf3-client --image {test_service}")
    os.system(f"kubectl config use-context {cl2Name}")
    os.system(
        f"kubectl run iperf3-server --image {test_service} --port 5000 -l app=iperf3-server -- -s -p 5000"
    )
    os.system("kubectl create service nodeport iperf3-server --tcp=5000:5000")


def try_connection():
    """ Tries connecting to iperf3 server from the iperf3 client """
    os.system(f"kubectl config use-context {cl1Name}")
    try:
        os.system("kubectl wait --for=condition=Ready pod/iperf3-client")
        direct_output = subprocess.check_output(
            f"kubectl exec -i iperf3-client -- iperf3 -c iperf3-server-{cl2Name} -p {destPort}",
            shell=True)
        print(f"{direct_output.decode()}")
        if "iperf Done" in direct_output.decode():
            return True
    except subprocess.CalledProcessError as e:
        return False
    return False


def test_create_cluster():
    """Tests connectivity using clusterlink APIs in KIND environment"""
    cleanup_clusters()
    setup_clusters()
    cluster1_manager = KubernetesManager(cl1Name)
    cluster2_manager = KubernetesManager(cl2Name)
    assert launch_clusterlink(cluster1_manager) is True
    assert launch_clusterlink(cluster2_manager) is True
    assert create_link(cluster1_manager, cluster2_manager) is True
    load_services()
    assert export_service(cluster2_service, cluster2_manager,
                          [destPort]) is True
    assert import_service(cluster2_service, cluster1_manager,
                          cluster2_manager.cluster_name, [destPort]) is True
    assert try_connection() is True
    cleanup_clusters()
