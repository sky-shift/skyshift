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
CL_INSTALL_DIR = os.path.join(CL_ROOT_DIR, "bin")

CL_PULL_CMD = (
    f"git clone https://github.com/praveingk/clusterlink.git {CL_DIRECTORY}/clusterlink"
)

# Clusterlink deployment commands to deploy on a cluster
CLA_FABRIC_CMD = ("cl-adm create fabric")
CLA_PEER_CMD = (
    "cl-adm create peer --name {cluster_name} --dataplane-type go --namespace {namespace} --container-registry quay.io/mcnet")
CL_UNDEPLOY_CMD = (
    "kubectl delete --context {cluster_name} -f {cluster_name}/k8s.yaml")
CL_DEPLOY_CMD = (
    "kubectl create --context {cluster_name} -f {cluster_name}/k8s.yaml")

# Clusterlink core CLI
# Initialization & Status
CL_INIT_CMD = (
    "gwctl init --id {cluster_name} --gwIP {cl_gw_ip} --gwPort {gw_port}  --certca {certca} --cert {cert} --key {key}"
)
CL_STATUS_CMD = ("gwctl get all --myid {cluster_name}")
# Link/Peer management
CL_LINK_CMD = (
    "gwctl create peer --myid {cluster_name} --name {peer} --host {target_ip} --port {target_port}"
)
CL_LINK_STATUS_CMD = ("gwctl get peer --myid {cluster_name} --name {peer}")
CL_LINK_DELETE_CMD = ("gwctl delete peer --myid {cluster_name} --name {peer}")
# Service Management
CL_EXPORT_CMD = (
    "gwctl create export --myid {cluster_name} --name {service_name} --host {service_target} --port {port}"
)
CL_IMPORT_CMD = (
    "gwctl create import --myid {cluster_name} --name {service_name} --host {service_name} --port {port}"
)
CL_BIND_CMD = (
    "gwctl create binding --myid {cluster_name} --import {service_name} --peer {peer}"
)
CL_POLICY_CMD = (
    "gwctl create policy --myid {cluster_name} --type access --policyFile {policy_file}"
)
CL_EXPORT_DELETE_CMD = (
    "gwctl delete export --myid {cluster_name} --name {service_name}")
CL_IMPORT_DELETE_CMD = (
    "gwctl delete import --myid {cluster_name} --name {service_name}")
CL_BIND_DELETE_CMD = (
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


# TODO @praveingk to change kubectl to kube APIs
def _wait_pod(cluster_name, name, namespace="default"):
    """Waits until the pod status is running"""
    podStatus = ""
    while ("Running" not in podStatus):
        cmd = f"kubectl get pods --context {cluster_name} -l app={name} -n {namespace} " + '--no-headers -o custom-columns=":status.phase"'
        podStatus = subprocess.check_output(cmd, shell=True).decode('utf-8')
        if ("Running" not in podStatus):
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
    except OSError as e:
        # Handle other errors
        cl_logger.info("Error in removing cluster's certs: {} - {}.".format(
            e.filename, e.strerror))


def _get_clusterlink_gw_target(cluster: str):
    """Gets the IP of the clusterlink gateway"""
    if cluster.startswith(KIND_PREFIX):
        clJson = json.loads(
            subprocess.getoutput(
                f'kubectl get nodes --context={cluster} -o json'))
        ip = clJson["items"][0]["status"]["addresses"][0]["address"]
        return ip, DEFAULT_CL_PORT_KIND
    # Clouds in general support load balancer to assign external IP
    clJson = json.loads(
        subprocess.getoutput(
            f"kubectl get svc --context {cluster} -l app=cl-dataplane  -o json"
        ))
    ip = clJson["items"][0]["status"]["loadBalancer"]["ingress"][0]["ip"]

    return ip, DEFAULT_CL_PORT


def _expose_clusterlink(cluster: str, port="443"):
    """Creates a loadbalancer to expose clusterlink to the external world."""
    if cluster.startswith(KIND_PREFIX):
        try:
            # Testing purpose on KIND Cluster
            subprocess.check_output(
                f"kubectl delete service --context={cluster} cl-dataplane",
                shell=True).decode('utf-8')
            subprocess.check_output(
                f"kubectl create service nodeport --context={cluster} cl-dataplane --tcp={port}:{port} --node-port=30443",
                shell=True).decode('utf-8')
            time.sleep(0.1)
            return
        except subprocess.CalledProcessError as e:
            print(f"Failed to create load balancer : {e.cmd}")
            raise e
    try:
        # Cleanup any previous stray loadbalancer initialized by earlier installation
        subprocess.check_output(
            f"kubectl delete svc --context={cluster} cl-dataplane-load-balancer", shell=True).decode('utf-8')
    except:
        # Ignore if not present
        pass
    try:
        # On Cloud/on-prem deployments, loadbalancer is usually provisioned
        ingress = ""
        subprocess.check_output(
            f"kubectl expose deployment --context={cluster} cl-dataplane --name=cl-dataplane-load-balancer --port={port} --target-port={port} --type=LoadBalancer",
            shell=True).decode('utf-8')
        while "ingress" not in ingress:
            clJson = json.loads(
                subprocess.getoutput(
                    f"kubectl get svc --context {cluster} -l app=cl-dataplane  -o json"
                ))
            ingress = clJson["items"][0]["status"]["loadBalancer"]
            time.sleep(0.1)
        cl_logger.info(f"Clusterlink Dataplane exposed in {ingress}")
    except subprocess.CalledProcessError as e:
        print(f"Failed to create load balancer : {e.cmd}")
        raise e


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
        cl_logger.info(f"Initializing Clusterlink gateway: {cl_init_cmd}")
        subprocess.check_output(cl_init_cmd, shell=True).decode('utf-8')
        while not _clusterlink_gateway_status(cluster):
            time.sleep(0.1)
        cl_policy_cmd = CL_POLICY_CMD.format(cluster_name=cluster,
                                             policy_file=os.path.join(
                                                 CL_DIRECTORY, POLICY_FILE))
        subprocess.check_output(cl_policy_cmd, shell=True).decode('utf-8')
    except subprocess.CalledProcessError as e:
        cl_logger.error(f"Failed to init Clusterlink gateway: {e.cmd}")
        raise e


def _build_clusterlink():
    """Builds Clusterlink binaries if its not already built"""
    try:
        subprocess.check_output("go mod tidy", shell=True,
                                cwd=CL_ROOT_DIR).decode('utf-8')
        subprocess.check_output("make build", shell=True,
                                cwd=CL_ROOT_DIR).decode('utf-8')
    except subprocess.CalledProcessError as e:
        cl_logger.error(f"Failed to build Clusterlink : {e.cmd}")
        raise e


def _install_clusterlink():
    """Installs Clusterlink if its not already present"""
    try:
        subprocess.getoutput(CL_PULL_CMD)
        if not os.path.exists(f"{CL_INSTALL_DIR}/cl-adm"):
            _build_clusterlink()
        cl_logger.info("Linking Clusterlink binary to path!")
        current_path = os.environ.get('PATH')
        os.environ['PATH'] = f"{CL_INSTALL_DIR}:{current_path}"
    except subprocess.CalledProcessError as e:
        cl_logger.error(f"Failed to link Clusterlink : {e.cmd}")
        raise e


def _launch_network_fabric():
    """Creates the network fabric (Root certificates) to enable secure communication between clusters"""
    try:
        cl_logger.info("Launching network fabric.")
        os.makedirs(CL_DIRECTORY, exist_ok=True)
        subprocess.check_output(CLA_FABRIC_CMD, shell=True,
                                cwd=CL_DIRECTORY).decode('utf-8')
        policy_file = json.dumps(POLICY_ALLOW_ALL, indent=2)
        with open(os.path.join(CL_DIRECTORY, POLICY_FILE), "w") as file:
            file.write(policy_file)
        return True
    except subprocess.CalledProcessError as e:
        cl_logger.error(f"Failed to launch network fabric : {e.cmd}")
        raise e


def _create_directional_link(source_cluster_name, target_cluster_name):
    """Creates a target peer cluster for a given source cluster"""
    if not check_link_status(source_cluster_name, target_cluster_name):
        try:
            target_cluster_ip, target_cluster_port = _get_clusterlink_gw_target(
                target_cluster_name)
            create_link_command = CL_LINK_CMD.format(
                cluster_name=source_cluster_name,
                peer=target_cluster_name,
                target_ip=target_cluster_ip,
                target_port=target_cluster_port)
            subprocess.check_output(create_link_command,
                                    shell=True).decode('utf-8')
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(
                f'Failed to establish a link between two clusters. {e.cmd.splitlines()[0]}'
            )
            raise e
    return True


def _delete_directional_link(source_cluster_name, target_cluster_name):
    """Deletes a target cluster as a peer"""
    if check_link_status(source_cluster_name, target_cluster_name):
        try:
            delete_link_command = CL_LINK_DELETE_CMD.format(
                cluster_name=source_cluster_name, peer=target_cluster_name)
            subprocess.check_output(delete_link_command,
                                    shell=True).decode('utf-8')
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            cl_logger.error(
                f'Failed delete a link between two clusters. {e.cmd.splitlines()[0]}'
            )
            raise e
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
    try:
        subprocess.check_output(cl_undeploy_command,
                                shell=True,
                                cwd=CL_DIRECTORY, timeout=60).decode('utf-8')  
    except subprocess.CalledProcessError:
        # Ignore if some components were not found
        pass
    try:    
        subprocess.check_output(cl_deploy_command,
                                shell=True,
                                cwd=CL_DIRECTORY).decode('utf-8')
    except subprocess.CalledProcessError as e:
        cl_logger.error(
            f"Failed to deploy clusterlink gateway on `{cluster_name}`: {e.cmd}") 

def launch_clusterlink(manager: KubernetesManager):
    """Launches clusterlink gateway on a cluster's namespace."""
    namespace = manager.namespace
    cluster_name = manager.cluster_name

    try:
        os.makedirs(CL_DIRECTORY, exist_ok=True)
        fabric_cert = os.path.join(CL_DIRECTORY, CERT)
        path = shutil.which("cl-adm")
        if path is None:
            _install_clusterlink()
        if os.path.exists(fabric_cert) != True:
            cl_logger.info(f"Launching network fabric!")
            _launch_network_fabric()
    except subprocess.CalledProcessError as e:
        cl_logger.error(f"Failed to Initiate Clusterlink : {e.cmd}")
        raise e
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
    except subprocess.CalledProcessError as e:
        cl_logger.error(
            f"Failed to launch network on `{cluster_name}`: {e.cmd}")
        raise e


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
    # TODO : @praveingk use namespace-local cluster-cluster links
    # cluster_name would then be defined by cluster_name+namespace

    source_namespace = source_manager.namespace
    source_cluster_name = source_manager.cluster_name

    target_namespace = target_manager.namespace
    target_cluster_name = target_manager.cluster_name
    try:
        _create_directional_link(source_cluster_name, target_cluster_name)
        _create_directional_link(target_cluster_name, source_cluster_name)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        return False
    return True


def delete_link(source_manager: KubernetesManager,
                target_manager: KubernetesManager):
    """Deletes a link between two clusters."""
    source_namespace = source_manager.namespace
    source_cluster_name = source_manager.cluster_name

    target_namespace = target_manager.namespace
    target_cluster_name = target_manager.cluster_name
    try:
        _delete_directional_link(source_cluster_name, target_cluster_name)
        _delete_directional_link(target_cluster_name, source_cluster_name)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        return False
    return True


def export_service(service_name: str, manager: KubernetesManager,
                   ports: List[int]):
    """Exposes/exports a service from the cluster to its peers"""
    # TODO : @praveingk use namespace speific to cluster
    namespace = manager.namespace
    cluster_name = manager.cluster_name
    expose_service_name = f'{service_name}-{cluster_name}'
    cl_logger.info(
        f"Exporting service {expose_service_name} from {cluster_name}")
    try:
        export_cmd = CL_EXPORT_CMD.format(cluster_name=cluster_name,
                                          service_name=expose_service_name,
                                          service_target=service_name,
                                          port=ports[0])
        subprocess.check_output(export_cmd, shell=True).decode('utf-8')
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        cl_logger.error(f'Failed to expose service. {e.cmd.splitlines()[0]}')
        return False


def import_service(service_name: str, manager: KubernetesManager, peer: str,
                   ports: List[int]):
    """Imports a service from a peered cluster"""
    cluster_name = manager.cluster_name
    import_service_name = f'{service_name}-{peer}'
    cl_logger.info(f"Importing service {import_service_name} from {peer}")
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
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        cl_logger.error(f'Failed to import service. {e.cmd.splitlines()[0]}')
        return False


def delete_export_service(service_name: str, manager: KubernetesManager):
    """Removes exporting a service from a cluster"""
    cluster_name = manager.cluster_name
    expose_service_name = f'{service_name}-{cluster_name}'
    cl_logger.info(
        f"Removing exported service {expose_service_name} from {cluster_name}")
    try:
        export_cmd = CL_EXPORT_DELETE_CMD.format(
            cluster_name=cluster_name, service_name=expose_service_name)
        subprocess.check_output(export_cmd, shell=True).decode('utf-8')
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        cl_logger.error(f'Failed to delete service. {e.cmd.splitlines()[0]}')
        return False


def delete_import_service(service_name: str, manager: KubernetesManager,
                          peer: str):
    """Removes importing a service from a peered cluster"""
    namespace = manager.namespace
    cluster_name = manager.cluster_name
    import_service_name = f'{service_name}-{peer}'
    cl_logger.info(
        f"Removing imported service {import_service_name} from {peer}")
    try:
        import_cmd = CL_IMPORT_DELETE_CMD.format(
            cluster_name=cluster_name, service_name=import_service_name)
        bind_cmd = CL_BIND_DELETE_CMD.format(cluster_name=cluster_name,
                                             service_name=import_service_name,
                                             peer=peer)
        subprocess.check_output(import_cmd, shell=True).decode('utf-8')
        subprocess.check_output(bind_cmd, shell=True).decode('utf-8')
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        cl_logger.error(
            f'Failed to delete imported service. {e.cmd.splitlines()[0]}')
        return False
