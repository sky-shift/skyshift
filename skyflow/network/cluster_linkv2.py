"""
Module to manage ClusterLink network operations.
"""
import json
import logging
import os
import shutil
import subprocess
import time
from typing import List

from skyflow.cluster_manager import KubernetesManager

logging.basicConfig(
    level=logging.INFO,
    format='%(name)s - %(asctime)s - %(levelname)s - %(message)s')

cl_logger = logging.getLogger("[Clusterlink Module]")
cl_logger.setLevel(logging.INFO)
CL_DIRECTORY = os.path.expanduser('~/.skyconf/cl/')
POLICY_FILE = 'allowAll.json'
CERT = "cert.pem"
KEY = "key.pem"
KIND_PREFIX = "kind-"
DEFAULT_CL_PORT = 443
DEFAULT_CL_PORT_KIND = 30443

CL_ROOT_DIR = os.path.join(CL_DIRECTORY, "clusterlink")
CL_INSTALL_DIR = os.path.join(CL_ROOT_DIR, "bin/")

CL_PULL_CMD = (
    f"git clone -b skyflow https://github.com/praveingk/clusterlink.git {CL_DIRECTORY}/clusterlink"
)

# Clusterlink deployment commands to deploy on a cluster
CLA_FABRIC_CMD = (CL_INSTALL_DIR + "cl-adm create fabric")
CLA_PEER_CMD = (CL_INSTALL_DIR +
                "cl-adm create peer --name {cluster_name} --dataplane-type go "
                "--namespace {namespace} --container-registry quay.io/mcnet")
CL_UNDEPLOY_CMD = ("kubectl delete --context {cluster_name} -f " +
                   CL_DIRECTORY + "{cluster_name}/k8s.yaml --wait=true  2>&1")
CL_DEPLOY_CMD = (
    "kubectl create --context {cluster_name} -f {cluster_name}/k8s.yaml")

# Clusterlink core CLI
# Initialization & Status
CL_INIT_CMD = (
    CL_INSTALL_DIR + "gwctl init --id {cluster_name} --gwIP {cl_gw_ip}"
    " --gwPort {gw_port}  --certca {certca} --cert {cert} --key {key}")
CL_STATUS_CMD = (CL_INSTALL_DIR + "gwctl get all --myid {cluster_name}")
# Link/Peer management
CL_LINK_CMD = (
    CL_INSTALL_DIR +
    "gwctl create peer --myid {cluster_name} --name {peer} --host {target_ip} --port {target_port}"
)
CL_LINK_STATUS_CMD = (CL_INSTALL_DIR +
                      "gwctl get peer --myid {cluster_name} --name {peer}")
CL_LINK_DELETE_CMD = (CL_INSTALL_DIR +
                      "gwctl delete peer --myid {cluster_name} --name {peer}")
# Service Management
CL_EXPORT_CMD = (
    CL_INSTALL_DIR +
    "gwctl create export --myid {cluster_name} --name {service_name}"
    " --host {service_target} --port {port}")
CL_IMPORT_CMD = (
    CL_INSTALL_DIR +
    "gwctl create import --myid {cluster_name} --name {service_name}"
    " --host {service_name} --port {port}")
CL_BIND_CMD = (
    CL_INSTALL_DIR +
    "gwctl create binding --myid {cluster_name} --import {service_name} --peer {peer}"
)
CL_POLICY_CMD = (
    CL_INSTALL_DIR +
    "gwctl create policy --myid {cluster_name} --type access --policyFile {policy_file}"
)
CL_EXPORT_DELETE_CMD = (
    CL_INSTALL_DIR +
    "gwctl delete export --myid {cluster_name} --name {service_name}")
CL_IMPORT_DELETE_CMD = (
    CL_INSTALL_DIR +
    "gwctl delete import --myid {cluster_name} --name {service_name}")
CL_BIND_DELETE_CMD = (
    CL_INSTALL_DIR +
    "gwctl delete binding --myid {cluster_name} --import {service_name} --peer {peer}"
)

POLICY_ALLOW_ALL = {
    "name": "allow-all",
    "privileged": False,
    "action": "allow",
    "from": [{
        "workloadSelector": {}
    }],
    "to": [{
        "workloadSelector": {}
    }]
}


# @praveingk to change kubectl to kube APIs
def _wait_pod(cluster_name, name, namespace="default"):
    """Waits until the pod status is running"""
    pod_status = ""
    while "Running" not in pod_status:
        cmd = (f"kubectl get pods --context {cluster_name}"
               f" -l app={name} -n {namespace} " +
               '--no-headers -o custom-columns=":status.phase"')
        pod_status = subprocess.check_output(cmd, shell=True).decode('utf-8')
        if "Running" not in pod_status:
            time.sleep(0.1)
        else:
            break


def _clusterlink_gateway_status(cluster_name: str):
    """Checks the status of clusterlink gaterway"""
    check_status_command = CL_STATUS_CMD.format(cluster_name=cluster_name)
    status_output = subprocess.getoutput(check_status_command)
    if 'Error' in status_output or 'not found' in status_output:
        return False
    return True


def _remove_cluster_certs(cluster_name: str):
    """Deletes cluster's previous certificates"""
    try:
        shutil.rmtree(os.path.join(CL_DIRECTORY, cluster_name))
    except FileNotFoundError:
        # Ignore the error if the directory doesn't exist
        pass
    except OSError as error:
        # Handle other errors
        cl_logger.info("Error in removing cluster's certs: %s - %s.",
                       error.filename, error.strerror)


def _get_clusterlink_gw_target(cluster: str):
    """Gets the IP of the clusterlink gateway"""
    if cluster.startswith(KIND_PREFIX):
        cl_json = json.loads(
            subprocess.getoutput(
                f'kubectl get nodes --context={cluster} -o json'))
        target = cl_json["items"][0]["status"]["addresses"][0]["address"]
        return target, DEFAULT_CL_PORT_KIND
    # Clouds in general support load balancer to assign external IP
    cl_json = json.loads(
        subprocess.getoutput(
            f"kubectl get svc --context {cluster} -l app=cl-dataplane  -o json"
        ))
    target = cl_json["items"][0]["status"]["loadBalancer"]["ingress"][0]["ip"]

    return target, DEFAULT_CL_PORT


def _expose_clusterlink(cluster: str, port="443"):
    """Creates a loadbalancer to expose clusterlink to the external world."""
    if cluster.startswith(KIND_PREFIX):
        try:
            # Testing purpose on KIND Cluster
            subprocess.check_output(
                f"kubectl delete service --context={cluster} cl-dataplane --wait=true",
                shell=True).decode('utf-8')
            subprocess.check_output(
                f"kubectl create service nodeport --context={cluster} cl-dataplane"
                f" --tcp={port}:{port} --node-port=30443",
                shell=True).decode('utf-8')
            time.sleep(5)
            return
        except subprocess.CalledProcessError as error:
            print("Failed to create load balancer : %s", error.cmd)
            raise error
    # Cleanup any previous stray loadbalancer initialized by earlier installation
    subprocess.getoutput(
        f"kubectl delete svc --context={cluster} cl-dataplane-load-balancer --wait=true 2>&1"
    )
    try:
        # On Cloud/on-prem deployments, loadbalancer is usually provisioned
        ingress = ""
        subprocess.check_output(
            f"kubectl expose deployment --context={cluster} cl-dataplane"
            f" --name=cl-dataplane-load-balancer --port={port}"
            f" --target-port={port} --type=LoadBalancer",
            shell=True).decode('utf-8')
        while "ingress" not in ingress:
            cl_json = json.loads(
                subprocess.getoutput(
                    f"kubectl get svc --context {cluster} -l app=cl-dataplane  -o json"
                ))
            ingress = cl_json["items"][0]["status"]["loadBalancer"]
            time.sleep(1)
        cl_logger.info("Clusterlink Dataplane exposed in %s", ingress)
    except subprocess.CalledProcessError as error:
        print("Failed to create load balancer : %s", error.cmd)
        raise error


def _init_clusterlink_gateway(cluster: str):
    """Initializes the Clusterlink gateway API server and adds policy to allow communication"""
    try:
        certca = os.path.join(CL_DIRECTORY, CERT)
        cert = os.path.join(CL_DIRECTORY, cluster, CERT)
        key = os.path.join(CL_DIRECTORY, cluster, KEY)
        gw_ip, gw_port = _get_clusterlink_gw_target(cluster)

        cl_init_cmd = CL_INIT_CMD.format(cluster_name=cluster,
                                         cl_gw_ip=gw_ip,
                                         gw_port=gw_port,
                                         certca=certca,
                                         cert=cert,
                                         key=key)
        cl_logger.info("Initializing Clusterlink gateway: %s", cl_init_cmd)
        subprocess.check_output(cl_init_cmd, shell=True).decode('utf-8')
        while not _clusterlink_gateway_status(cluster):
            time.sleep(0.1)
        cl_policy_cmd = CL_POLICY_CMD.format(cluster_name=cluster,
                                             policy_file=os.path.join(
                                                 CL_DIRECTORY, POLICY_FILE))
        subprocess.check_output(cl_policy_cmd, shell=True).decode('utf-8')
    except subprocess.CalledProcessError as error:
        cl_logger.error("Failed to init Clusterlink gateway: %s", error.cmd)
        raise error


def _build_clusterlink():
    """Builds Clusterlink binaries if its not already built"""
    try:
        subprocess.check_output("go mod tidy", shell=True,
                                cwd=CL_ROOT_DIR).decode('utf-8')
        subprocess.check_output("make build", shell=True,
                                cwd=CL_ROOT_DIR).decode('utf-8')
    except subprocess.CalledProcessError as error:
        cl_logger.error("Failed to build Clusterlink : %s", error.cmd)
        raise error


def _install_clusterlink():
    """Installs Clusterlink if its not already present"""
    try:
        subprocess.getoutput(CL_PULL_CMD)
        _build_clusterlink()
    except subprocess.CalledProcessError as error:
        cl_logger.error("Failed to link Clusterlink : %s", error.cmd)
        raise error


def _launch_network_fabric():
    """Creates the network fabric (Root certificates)
       to enable secure communication between clusters"""
    try:
        cl_logger.info("Launching network fabric.")
        os.makedirs(CL_DIRECTORY, exist_ok=True)
        subprocess.check_output(CLA_FABRIC_CMD, shell=True,
                                cwd=CL_DIRECTORY).decode('utf-8')
        policy_file = json.dumps(POLICY_ALLOW_ALL, indent=2)
        with open(os.path.join(CL_DIRECTORY, POLICY_FILE), "w") as file:
            file.write(policy_file)
        return True
    except subprocess.CalledProcessError as error:
        cl_logger.error("Failed to launch network fabric : %s", error.cmd)
        raise error


def _create_directional_link(cluster_name, peer):
    """Creates a target peer cluster for a given source cluster"""
    if not check_link_status(cluster_name, peer):
        try:
            peer_cluster_ip, peer_cluster_port = _get_clusterlink_gw_target(
                peer)
            create_link_command = CL_LINK_CMD.format(
                cluster_name=cluster_name,
                peer=peer,
                target_ip=peer_cluster_ip,
                target_port=peer_cluster_port)
            subprocess.check_output(create_link_command,
                                    shell=True).decode('utf-8')
        except (subprocess.CalledProcessError,
                subprocess.TimeoutExpired) as error:
            cl_logger.error(
                "Failed to establish a link between two clusters : %s",
                error.cmd.splitlines()[0])
            raise error
    return True


def _delete_directional_link(cluster_name, peer):
    """Deletes a cluster as a peer"""
    if check_link_status(cluster_name, peer):
        try:
            delete_link_command = CL_LINK_DELETE_CMD.format(
                cluster_name=cluster_name, peer=peer)
            subprocess.check_output(delete_link_command,
                                    shell=True).decode('utf-8')
        except (subprocess.CalledProcessError,
                subprocess.TimeoutExpired) as error:
            cl_logger.error("Failed delete a link between two clusters : %s",
                            error.cmd.splitlines()[0])
            raise error
    return True


def status_network(manager: KubernetesManager):
    """Checks if clusterlink gateway is running on a cluster."""
    cluster_name = manager.cluster_name
    # Check Clusterlink status.
    return _clusterlink_gateway_status(cluster_name)


def _deploy_clusterlink_gateway(cluster_name: str):
    """Deploys the clusterlink gateway and its components on a cluster."""
    cl_undeploy_command = CL_UNDEPLOY_CMD.format(cluster_name=cluster_name)
    cl_deploy_command = CL_DEPLOY_CMD.format(cluster_name=cluster_name)
    subprocess.getoutput(cl_undeploy_command)
    # Workaround to wait for gwctl to terminate
    # (this pod would be gone in upcoming release)
    subprocess.getoutput(
        f"kubectl wait --for=delete pod/gwctl --context={cluster_name}")
    try:
        subprocess.check_output(cl_deploy_command,
                                shell=True,
                                cwd=CL_DIRECTORY).decode('utf-8')
    except subprocess.CalledProcessError as error:
        cl_logger.error("Failed to deploy clusterlink gateway on  %s : %s",
                        cluster_name, error.cmd)


def launch_clusterlink(manager: KubernetesManager):
    """Launches clusterlink gateway on a cluster's namespace."""
    namespace = manager.namespace
    cluster_name = manager.cluster_name

    try:
        os.makedirs(CL_DIRECTORY, exist_ok=True)
        fabric_cert = os.path.join(CL_DIRECTORY, CERT)
        if not os.path.exists(f"{CL_INSTALL_DIR}/cl-adm"):
            _install_clusterlink()
        if os.path.exists(fabric_cert) is not True:
            cl_logger.info("Launching network fabric!")
            _launch_network_fabric()
    except subprocess.CalledProcessError as error:
        cl_logger.error("Failed to Initiate Clusterlink : %s", error.cmd)
        raise error
    try:
        cl_peer_command = CLA_PEER_CMD.format(cluster_name=cluster_name,
                                              namespace=namespace)
        _remove_cluster_certs(cluster_name)
        subprocess.check_output(cl_peer_command, shell=True,
                                cwd=CL_DIRECTORY).decode('utf-8')
        _deploy_clusterlink_gateway(cluster_name)
        _wait_pod(cluster_name, "cl-controlplane")
        _wait_pod(cluster_name, "cl-dataplane")
        _expose_clusterlink(cluster_name)
        _init_clusterlink_gateway(cluster_name)
        return True
    except subprocess.CalledProcessError as error:
        cl_logger.error("Failed to launch network on  %s : %s", cluster_name,
                        error.cmd)
        raise error


def check_link_status(source_cluster_name: str, target_cluster_name: str):
    """Checks if a link exists between two clusters."""
    status_link_command = CL_LINK_STATUS_CMD.format(
        cluster_name=source_cluster_name, peer=target_cluster_name)
    status_output = subprocess.getoutput(status_link_command)
    if 'Error' in status_output or 'not found' in status_output:
        return False
    return True


def create_link(source_manager: KubernetesManager,
                target_manager: KubernetesManager):
    """Creates a link between two clusters."""
    # @praveingk use namespace-local cluster-cluster links
    # cluster_name would then be defined by cluster_name+namespace

    source_cluster_name = source_manager.cluster_name
    target_cluster_name = target_manager.cluster_name
    try:
        _create_directional_link(source_cluster_name, target_cluster_name)
        _create_directional_link(target_cluster_name, source_cluster_name)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False
    return True


def delete_link(source_manager: KubernetesManager,
                target_manager: KubernetesManager):
    """Deletes a link between two clusters."""
    source_cluster_name = source_manager.cluster_name
    target_cluster_name = target_manager.cluster_name
    try:
        _delete_directional_link(source_cluster_name, target_cluster_name)
        _delete_directional_link(target_cluster_name, source_cluster_name)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False
    return True


def export_service(service_name: str, manager: KubernetesManager,
                   ports: List[int]):
    """Exposes/exports a service from the cluster to its peers"""
    # @praveingk use namespace speific to cluster
    cluster_name = manager.cluster_name
    expose_service_name = f'{service_name}-{cluster_name}'
    cl_logger.info(
        "Exporting service %s from %s", expose_service_name, cluster_name)
    try:
        export_cmd = CL_EXPORT_CMD.format(cluster_name=cluster_name,
                                          service_name=expose_service_name,
                                          service_target=service_name,
                                          port=ports[0])
        subprocess.check_output(export_cmd, shell=True).decode('utf-8')
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        cl_logger.error("Failed to expose service : %s",
                        error.cmd.splitlines()[0])
        return False


def import_service(service_name: str, manager: KubernetesManager, peer: str,
                   ports: List[int]):
    """Imports a service from a peered cluster"""
    cluster_name = manager.cluster_name
    import_service_name = f'{service_name}-{peer}'
    cl_logger.info("Importing service %s from %s", import_service_name, peer)
    try:
        import_cmd = CL_IMPORT_CMD.format(cluster_name=cluster_name,
                                          service_name=import_service_name,
                                          port=ports[0])
        bind_cmd = CL_BIND_CMD.format(cluster_name=cluster_name,
                                      service_name=import_service_name,
                                      peer=peer)
        subprocess.check_output(import_cmd, shell=True).decode('utf-8')
        subprocess.check_output(bind_cmd, shell=True).decode('utf-8')
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        cl_logger.error("Failed to import service : %s",
                        error.cmd.splitlines()[0])
        return False


def delete_export_service(service_name: str, manager: KubernetesManager):
    """Removes exporting a service from a cluster"""
    cluster_name = manager.cluster_name
    expose_service_name = f'{service_name}-{cluster_name}'
    cl_logger.info("Removing exported service %s from %s", expose_service_name,
                   cluster_name)
    try:
        export_cmd = CL_EXPORT_DELETE_CMD.format(
            cluster_name=cluster_name, service_name=expose_service_name)
        subprocess.check_output(export_cmd, shell=True).decode('utf-8')
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        cl_logger.error("Failed to delete service : %s",
                        error.cmd.splitlines()[0])
        return False


def delete_import_service(service_name: str, manager: KubernetesManager,
                          peer: str):
    """Removes importing a service from a peered cluster"""
    cluster_name = manager.cluster_name
    import_service_name = f'{service_name}-{peer}'
    cl_logger.info("Removing imported service %s from %s", import_service_name,
                   peer)
    try:
        import_cmd = CL_IMPORT_DELETE_CMD.format(
            cluster_name=cluster_name, service_name=import_service_name)
        bind_cmd = CL_BIND_DELETE_CMD.format(cluster_name=cluster_name,
                                             service_name=import_service_name,
                                             peer=peer)
        subprocess.check_output(import_cmd, shell=True).decode('utf-8')
        subprocess.check_output(bind_cmd, shell=True).decode('utf-8')
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        cl_logger.error("Failed to delete imported service: %s",
                        error.cmd.splitlines()[0])
        return False
