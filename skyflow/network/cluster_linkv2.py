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

from kubernetes import client, config, utils

import skyflow.utils as skyflow_utils
from skyflow.cluster_manager import KubernetesManager

logging.basicConfig(
    level=logging.INFO,
    format='%(name)s - %(asctime)s - %(levelname)s - %(message)s')

cl_logger = logging.getLogger("[Clusterlink Module]")
cl_logger.setLevel(logging.INFO)
CL_DIRECTORY = os.path.expanduser('~/.skyconf/cl/')
CL_FABRIC_DIRECTORY = os.path.expanduser('~/.skyconf/cl/default_fabric/')
INSTALL_LOCK_PATH = os.path.expanduser('~/.skyconf/install.lock')

POLICY_FILE = 'allowAll.json'
CERT = "cert.pem"
KEY = "key.pem"
KIND_PREFIX = "kind-"
DEFAULT_CL_PORT = 443
DEFAULT_CL_PORT_KIND = 30443
CL_VERSION = "v0.2.1"
CL_DATAPLANE = "cl-dataplane"
CL_SERVICE = "cl-dataplane-load-balancer"
CL_INSTALL_DIR = os.path.expanduser("~/.local/bin/")

CL_INSTALL_CMD = (
    "export VERSION={version};"
    "curl -sL "
    "https://github.com/clusterlink-net/clusterlink/releases/download/"
    "{version}/clusterlink.sh | sh ")

# Clusterlink deployment commands to deploy on a cluster
CLA_FABRIC_CMD = ("clusterlink create fabric")

CLA_PEER_CMD = (
    "clusterlink create peer-cert --name {cluster_name} --namespace {namespace} --tag {tag}"
)
CLA_PEER_CERT_CMD = (
    "clusterlink create peer-cert --name {cluster_name}"
)
CLA_DEPLOY_CMD = (
    "clusterlink deploy peer --name {cluster_name} --namespace {namespace} --tag {tag} --start none"
)

# Clusterlink core CLI
# Initialization & Status
CL_INIT_CMD = (
    "gwctl init --id {cluster_name} --gwIP {cl_gw_ip}"
    " --gwPort {gw_port}  --certca {certca} --cert {cert} --key {key}")
CL_STATUS_CMD = ("gwctl get all --myid {cluster_name}")
# Link/Peer management
CL_LINK_CMD = (
    "gwctl create peer --myid {cluster_name} --name {peer} --host {target_ip} --port {target_port}"
)
CL_LINK_STATUS_CMD = ("gwctl get peer --myid {cluster_name} --name {peer}")
CL_LINK_DELETE_CMD = ("gwctl delete peer --myid {cluster_name} --name {peer}")
# Service Management
CL_EXPORT_CMD = (
    "gwctl create export --myid {cluster_name} --name {service_name}"
    " --host {service_target} --port {port}")
CL_IMPORT_CMD = (
    "gwctl create import --myid {cluster_name} --name {service_name}"
    " --port {port} --peer {peer} --merge")
CL_GET_IMPORT_CMD = (
    "gwctl get import --myid {cluster_name} --name {service_name}")
CL_UPDATE_IMPORT_CMD = (
    "gwctl update import --myid {cluster_name} --name {service_name}"
    " --port {port} --peer {peer} --merge")

CL_POLICY_CMD = (
    "gwctl create policy --myid {cluster_name} --policyFile {policy_file}"
)
CL_EXPORT_DELETE_CMD = (
    "gwctl delete export --myid {cluster_name} --name {service_name}")
CL_IMPORT_DELETE_CMD = (
    "gwctl delete import --myid {cluster_name} --name {service_name}")

POLICY_ALLOW_ALL = {
    "name": "allow-all",
    "spec": {
        "privileged": False,
        "action": "allow",
        "from": [{
            "workloadSelector": {}
        }],
        "to": [{
            "workloadSelector": {}
        }]
    }
}

def _install_lock_acquire():
    """Blocks until lock using a file"""
    while os.path.exists(INSTALL_LOCK_PATH):
        time.sleep(0.1)
    open(INSTALL_LOCK_PATH,'w').close()

def _install_lock_release():
    os.remove(INSTALL_LOCK_PATH)

def _wait_for_ready_deployment(k8s_api_client: client.ApiClient,
                               name,
                               namespace="default",
                               timeout_seconds=300):
    """Waits until the pod status is running"""
    start_time = time.time()
    end_time = start_time + timeout_seconds
    core_api = client.AppsV1Api(api_client=k8s_api_client)
    while time.time() < end_time:
        try:
            deployment = core_api.read_namespaced_deployment(
                name, namespace=namespace)
        except client.exceptions.ApiException:
            continue
        if deployment.status.ready_replicas == deployment.status.replicas:
            return True
        time.sleep(0.1)


def _parse_clusterlink_op(output: str):
    if 'object already exists' in output:
        return True
    if 'Error' in output:
        return False
    return True


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
        shutil.rmtree(os.path.join(CL_FABRIC_DIRECTORY, cluster_name))
    except FileNotFoundError:
        # Ignore the error if the directory doesn't exist
        pass
    except OSError as error:
        # Handle other errors
        cl_logger.info("Error in removing cluster's certs: %s - %s.",
                       error.filename, error.strerror)


def _get_clusterlink_gw_target(cluster: str, namespace="default"):
    """Gets the IP of the clusterlink gateway"""
    core_api = client.CoreV1Api(
        config.new_client_from_config(
            context=skyflow_utils.unsanitize_cluster_name(cluster)))
    if cluster.startswith(KIND_PREFIX):
        nodes = core_api.list_node()
        return nodes.items[0].status.addresses[0].address, DEFAULT_CL_PORT_KIND
    # Clouds in general support load balancer to assign external IP
    service = core_api.read_namespaced_service(CL_SERVICE, namespace)
    if service.status.load_balancer and service.status.load_balancer.ingress:
        return service.status.load_balancer.ingress[0].ip, DEFAULT_CL_PORT
    return None, None


def _expose_clusterlink(k8s_api_client: client.ApiClient,
                        cluster,
                        namespace: str,
                        port=443):
    """Creates a loadbalancer to expose clusterlink to the external world."""
    core_api = client.CoreV1Api(k8s_api_client)
    if cluster.startswith(KIND_PREFIX):
        try:
            # Testing purpose on KIND Cluster
            core_api.delete_namespaced_service(CL_DATAPLANE, namespace)
            service_body = client.V1Service(
                metadata=client.V1ObjectMeta(name=CL_DATAPLANE),
                spec=client.V1ServiceSpec(type="NodePort",
                                          selector={"app": CL_DATAPLANE},
                                          ports=[
                                              client.V1ServicePort(
                                                  protocol="TCP",
                                                  port=port,
                                                  target_port=port,
                                                  node_port=30443,
                                              )
                                          ]))
            core_api.create_namespaced_service(namespace, service_body)
            time.sleep(5)
            return
        except subprocess.CalledProcessError as error:
            cl_logger.error("Failed to create load balancer : %s",
                            error.stderr.decode())
            raise error
    try:
        # On Cloud/on-prem deployments, loadbalancer is usually provisioned
        service_body = client.V1Service(
            metadata=client.V1ObjectMeta(name=CL_SERVICE),
            spec=client.V1ServiceSpec(type="LoadBalancer",
                                      selector={"app": CL_DATAPLANE},
                                      ports=[
                                          client.V1ServicePort(
                                              protocol="TCP",
                                              port=port,
                                              target_port=port,
                                          )
                                      ]))
        core_api.create_namespaced_service(namespace, service_body)
    except client.ApiException as error:
        if error.status == 409:  # Conflict, service already exists
            core_api.patch_namespaced_service(name=CL_SERVICE,
                                              namespace=namespace,
                                              body=service_body)
        else:
            raise error
    while True:
        service = core_api.read_namespaced_service(CL_SERVICE, namespace)
        if service.status.load_balancer and service.status.load_balancer.ingress:
            return
        time.sleep(1)


def _init_clusterlink_gateway(cluster: str, namespace="default"):
    """Initializes the Clusterlink gateway API server and adds policy to allow communication"""
    try:
        certca = os.path.join(CL_FABRIC_DIRECTORY, CERT)
        cert = os.path.join(CL_FABRIC_DIRECTORY, cluster, CERT)
        key = os.path.join(CL_FABRIC_DIRECTORY, cluster, KEY)
        gw_ip, gw_port = _get_clusterlink_gw_target(cluster, namespace)

        cl_init_cmd = CL_INIT_CMD.format(cluster_name=cluster,
                                         cl_gw_ip=gw_ip,
                                         gw_port=gw_port,
                                         certca=certca,
                                         cert=cert,
                                         key=key)
        subprocess.check_output(cl_init_cmd,
                                shell=True,
                                stderr=subprocess.STDOUT).decode('utf-8')
        while not _clusterlink_gateway_status(cluster):
            time.sleep(0.1)
        cl_policy_cmd = CL_POLICY_CMD.format(cluster_name=cluster,
                                             policy_file=os.path.join(
                                                 CL_DIRECTORY, POLICY_FILE))
        subprocess.getoutput(cl_policy_cmd)
        cl_logger.info("Clusterlink Gateway Initialized & ready to link")
        return True
    except subprocess.CalledProcessError as error:
        cl_logger.error("Failed to init Clusterlink gateway: %s",
                        error.output.decode('utf-8'))
        raise error


def _install_clusterlink():
    """Installs Clusterlink if its not already present"""
    try:
        cl_logger.info("Installing clusterlink binary")
        cl_install_cmd = CL_INSTALL_CMD.format(version=CL_VERSION)
        subprocess.check_output(cl_install_cmd,
                                shell=True,
                                stderr=subprocess.STDOUT).decode('utf-8')
    except subprocess.CalledProcessError as error:
        cl_logger.error("Failed to install Clusterlink: %s",
                        error.output.decode('utf-8'))
        raise error


def _launch_network_fabric():
    """Creates the network fabric (Root certificates)
       to enable secure communication between clusters"""
    try:
        cl_logger.info("Launching network fabric")
        os.makedirs(CL_DIRECTORY, exist_ok=True)
        subprocess.check_output(CLA_FABRIC_CMD,
                                shell=True,
                                stderr=subprocess.STDOUT,
                                cwd=CL_DIRECTORY).decode('utf-8')
        policy_file = json.dumps(POLICY_ALLOW_ALL, indent=2)
        with open(os.path.join(CL_DIRECTORY, POLICY_FILE), "w") as file:
            file.write(policy_file)
        return True
    except subprocess.CalledProcessError as error:
        cl_logger.error("Failed to launch network fabric : %s",
                        error.output.decode('utf-8'))
        raise error


def _create_directional_link(cluster_name, peer):
    """Creates a target peer cluster for a given source cluster"""
    if check_link_status(cluster_name, peer):
        return True
    peer_cluster_ip, peer_cluster_port = _get_clusterlink_gw_target(peer)
    create_link_command = CL_LINK_CMD.format(cluster_name=cluster_name,
                                             peer=peer,
                                             target_ip=peer_cluster_ip,
                                             target_port=peer_cluster_port)
    output = subprocess.getoutput(create_link_command)
    if not _parse_clusterlink_op(output):
        cl_logger.error("Failed to establish a link between two clusters: %s",
                        output.splitlines()[0])
        return False
    return True


def _delete_directional_link(cluster_name, peer):
    """Deletes a cluster as a peer"""
    if not check_link_status(cluster_name, peer):
        return True
    delete_link_command = CL_LINK_DELETE_CMD.format(cluster_name=cluster_name,
                                                    peer=peer)
    output = subprocess.getoutput(delete_link_command)
    if not _parse_clusterlink_op(output):
        cl_logger.error("Failed to delete a link between two clusters: %s",
                        output.splitlines()[0])
        return False
    return True


def status_network(manager: KubernetesManager):
    """Checks if clusterlink gateway is running on a cluster."""
    cluster_name = manager.cluster_name
    # Check Clusterlink status.
    return _clusterlink_gateway_status(cluster_name)


def _deploy_clusterlink_gateway(k8s_api_client: client.ApiClient, cluster_name,
                                namespace: str):
    """Deploys the clusterlink gateway and its components on a cluster."""
    try:
        cl_logger.info("Deploying file %s", os.path.join(CL_FABRIC_DIRECTORY, cluster_name,
                                            "k8s.yaml"))
        utils.create_from_yaml(k8s_api_client,
                               os.path.join(CL_FABRIC_DIRECTORY, cluster_name,
                                            "k8s.yaml"),
                               namespace=namespace)
    except utils.FailToCreateError as error:
        for api_err in error.api_exceptions:
            if api_err.status == 409:  # Conflict, already exists
                pass
            else:
                raise error


def _deploy_clusterlink_k8s(cluster_name, namespace: str):
    """Deploys clusterlink gateway in Kubernetes cluster."""
    k8s_api_client = config.new_client_from_config(
        context=skyflow_utils.unsanitize_cluster_name(cluster_name))
    _deploy_clusterlink_gateway(k8s_api_client, cluster_name, namespace)
    _wait_for_ready_deployment(k8s_api_client, "cl-controlplane")
    _wait_for_ready_deployment(k8s_api_client, "cl-dataplane")
    _expose_clusterlink(k8s_api_client, cluster_name, namespace)
    cl_logger.info("Clusterlink successfully setup on %s", cluster_name)


def launch_clusterlink(manager: KubernetesManager):
    """Launches clusterlink gateway on a cluster's namespace."""
    namespace = manager.namespace
    cluster_name = manager.cluster_name
    _install_lock_acquire()
    try:
        cl_logger.info("Acquired Lock %s.. tring to install.", cluster_name)
        os.makedirs(CL_DIRECTORY, exist_ok=True)
        fabric_cert = os.path.join(CL_FABRIC_DIRECTORY, CERT)
        if not os.path.exists(f"{CL_INSTALL_DIR}/clusterlink"):
            _install_clusterlink()
        cl_logger.info(fabric_cert)
        if not os.path.exists(fabric_cert):
            cl_logger.info("Launching network fabric!")
            _launch_network_fabric()
    except subprocess.CalledProcessError as error:
        cl_logger.error("Failed to launch Clusterlink")
        raise error
    finally:
        _install_lock_release()
        cl_logger.info("Released Lock %s", cluster_name)
    try:

        cl_peer_command = CLA_PEER_CERT_CMD.format(cluster_name=cluster_name)
        cl_deploy_command = CLA_DEPLOY_CMD.format(cluster_name=cluster_name,
                                              namespace=namespace,
                                              tag=CL_VERSION)
        cl_logger.info("Doing clusterlink deploy : %s", cl_deploy_command)

        _remove_cluster_certs(cluster_name)
        subprocess.check_output(cl_peer_command,
                                shell=True,
                                stderr=subprocess.STDOUT,
                                cwd=CL_DIRECTORY).decode('utf-8')
        subprocess.check_output(cl_deploy_command,
                                shell=True,
                                stderr=subprocess.STDOUT,
                                cwd=CL_DIRECTORY).decode('utf-8')
        _deploy_clusterlink_k8s(cluster_name, namespace)
        _init_clusterlink_gateway(cluster_name, namespace)

        return True
    except subprocess.CalledProcessError as error:
        cl_logger.error("Failed to launch Clusterlink on  %s : %s",
                        cluster_name, error.output.decode('utf-8'))
        raise error


def check_link_status(source_cluster_name: str, target_cluster_name: str):
    """Checks if a link exists between two clusters."""
    status_link_command = CL_LINK_STATUS_CMD.format(
        cluster_name=source_cluster_name, peer=target_cluster_name)
    status_output = subprocess.getoutput(status_link_command)
    return _parse_clusterlink_op(status_output)


def create_link(source_manager: KubernetesManager,
                target_manager: KubernetesManager):
    """Creates a link between two clusters."""
    # Need to do  namespace-local cluster-cluster links
    # cluster_name would then be defined by cluster_name+namespace
    source_cluster_name = source_manager.cluster_name
    target_cluster_name = target_manager.cluster_name
    if not _create_directional_link(source_cluster_name, target_cluster_name):
        return False
    if not _create_directional_link(target_cluster_name, source_cluster_name):
        return False
    return True


def delete_link(source_manager: KubernetesManager,
                target_manager: KubernetesManager):
    """Deletes a link between two clusters."""
    source_cluster_name = source_manager.cluster_name
    target_cluster_name = target_manager.cluster_name
    if not _delete_directional_link(source_cluster_name, target_cluster_name):
        return False

    if not _delete_directional_link(target_cluster_name, source_cluster_name):
        return False
    return True


def export_service(service_name: str, manager: KubernetesManager,
                   ports: List[int]):
    """Exposes/exports a service from the cluster to its peers"""
    # @praveingk use namespace specific to cluster
    cluster_name = manager.cluster_name
    expose_service_name = f'{service_name}'
    cl_logger.info("Exporting service %s from %s", expose_service_name,
                   cluster_name)
    export_cmd = CL_EXPORT_CMD.format(cluster_name=cluster_name,
                                      service_name=expose_service_name,
                                      service_target=service_name,
                                      port=ports[0])
    output = subprocess.getoutput(export_cmd)
    if not _parse_clusterlink_op(output):
        cl_logger.error("Failed to export service: %s", output.splitlines()[0])
        return False
    return True

def _get_existing_import_clusters(service_name: str, cluster_name: str):
    """Gets the list of clusters a service is imported from"""
    sources : List[str]
    port = ""
    get_import_cmd = CL_GET_IMPORT_CMD.format(cluster_name=cluster_name,
                                      service_name=service_name)   
    output = subprocess.getoutput(get_import_cmd)
    if not _parse_clusterlink_op(output):
        return None, ""
    try:
        data = json.loads(output)
        port = data["spec"]["port"]
        sources = []
        for source in data["spec"]["sources"]:
            peer = source["peer"]
            sources.append(peer)
        return sources, port
    except json.JSONDecodeError as error:
        cl_logger.error("Error decoding imports: %s", error)
        return None, ""
        


def import_service(service_name: str, manager: KubernetesManager, peer: str,
                   ports: List[int]):
    """Imports a service from a peered cluster"""
    cluster_name = manager.cluster_name
    output = ""
    sources, _ = _get_existing_import_clusters(service_name, cluster_name)
    if sources is not None:
        # Update existing import
        for source in sources:
            peer += "," + source
        cl_logger.info("Updating imported service %s from %s", service_name, peer)
        import_cmd = CL_UPDATE_IMPORT_CMD.format(cluster_name=cluster_name,
                                        service_name=service_name,
                                        port=ports[0],
                                        peer=peer)
        cl_logger.info("%s", import_cmd)
        output = subprocess.getoutput(import_cmd)       
    else:
        # New import
        cl_logger.info("Importing service %s from %s", service_name, peer)
        import_cmd = CL_IMPORT_CMD.format(cluster_name=cluster_name,
                                        service_name=service_name,
                                        port=ports[0],
                                        peer=peer)
        output = subprocess.getoutput(import_cmd)

    if not _parse_clusterlink_op(output):
        cl_logger.error("Failed to import service: %s", output.splitlines()[0])
        return False
    return True


def delete_export_service(service_name: str, manager: KubernetesManager):
    """Removes exporting a service from a cluster"""
    cluster_name = manager.cluster_name
    cl_logger.info("Removing exported service %s from %s", service_name,
                   cluster_name)
    export_cmd = CL_EXPORT_DELETE_CMD.format(cluster_name=cluster_name,
                                             service_name=service_name)
    output = subprocess.getoutput(export_cmd)
    if not _parse_clusterlink_op(output):
        cl_logger.error("Failed to delete export of service: %s",
                        output.splitlines()[0])
        return False
    return True


def delete_import_service(service_name: str, manager: KubernetesManager,
                          peer: str):
    """Removes importing a service from a peered cluster"""
    cluster_name = manager.cluster_name
    output = ""
    sources, port = _get_existing_import_clusters(service_name, cluster_name)
    if sources is not None and len(sources) > 1:
        # Update existing import to remove the specific peer from source
        new_peers = ""
        for source in sources:
            if source != peer:
                new_peers += source + ","
        cl_logger.info("Updating imported service %s from %s", service_name, new_peers)
        import_cmd = CL_UPDATE_IMPORT_CMD.format(cluster_name=cluster_name,
                                        service_name=service_name,
                                        port=port,
                                        peer=new_peers)
        output = subprocess.getoutput(import_cmd)             
    else:
        # Remove the import as it has only one source
        cl_logger.info("Removing imported service %s from %s", service_name,
                    peer)
        import_cmd = CL_IMPORT_DELETE_CMD.format(cluster_name=cluster_name,
                                                service_name=service_name)
        output = subprocess.getoutput(import_cmd)

    if not _parse_clusterlink_op(output):
        cl_logger.error("Failed to delete import of service: %s",
                        output.splitlines()[0])
        return False
    return True
