# For now, we implement linking of clusters using Skupper.
import os
import subprocess
import shutil
from typing import List
import time
import json
from skyflow.cluster_manager import Manager

CL_DIRECTORY = os.path.expanduser('~/.skym/cl/')
POLICY_FILE = 'allowAll.json'
CERT = "cert.pem"
KEY = "key.pem"
KIND_PREFIX = "kind-"
DEFAULT_CL_PORT = 443
DEFAULT_CL_PORT_KIND = 30443

CL_INSTALL_DIR = CL_DIRECTORY+ "clusterlink/bin/"

SKUPPER_INSTALL_CMD = 'skupper init --context {cluster_name} --namespace {namespace}'
SKUPPER_STATUS_CMD = 'skupper status --context {cluster_name} --namespace {namespace}'
SKUPPER_TOKEN_CMD = 'skupper token create ~/.skym/link_secrets/{name}.token --context {cluster_name} --namespace {namespace}'
SKUPPER_LINK_CREATE_CMD = 'skupper link create ~/.skym/link_secrets/{name}.token --context {cluster_name} --namespace {namespace} --name {name}'
SKUPPER_LINK_DELETE_CMD = 'skupper link delete {name} --context {cluster_name} --namespace {namespace}'
SKUPPER_LINK_STATUS_CMD = 'skupper link status {name} --context {cluster_name} --namespace {namespace}'

CL_INSTALL_CMD = './skyflow/network/clusterlink_install.sh {dir}'
CLA_FABRIC_CMD = 'cl-adm create fabric'
CLA_PEER_CMD = 'cl-adm create peer --name {cluster_name}'
CL_DEPLOY_CMD = 'kubectl create -f {cluster_name}/k8s.yaml'

CL_INIT_CMD = 'gwctl init --id {cluster_name} --gwIP {cl_gw_ip} --gwPort {gw_port}  --certca {certca} --cert {cert} --key {key}'
CL_LINK_CMD = 'gwctl create peer --myid {cluster_name} --name {peer} --host {target_ip} --port {target_port}'
CL_LINK_STATUS_CMD = 'gwctl get peer --myid {cluster_name} --name {peer}'
CL_LINK_DELETE_CMD = 'gwctl delete peer --myid {cluster_name} --name {peer}'

CL_EXPORT_CMD = 'gwctl create export --myid {cluster_name} --name {service_name} --host {service_target} --port {port}'
CL_IMPORT_CMD = 'gwctl create import --myid {cluster_name} --name {service_name} --host {service_name} --port {port}'
CL_BIND_CMD = 'gwctl create binding --myid {cluster_name} --import {service_name} --peer {peer}'
CL_POLICY_CMD = 'gwctl create policy --myid {cluster_name} --type access --policyFile {policy_file}'

CLUSTER_IP_CMD = 'kubectl get nodes -o \"jsonpath={.items[0].status.addresses[0].address}\"'
KUBE_CONTEXT_CMD = 'kubectl config use-context {cluster_name}'


policy_allow_all = {
    "name": "allow-all",
    "privileged": False,
    "action": "allow",
    "from": [
        {
            "workloadSelector": {}
        }
    ],
    "to": [
        {
            "workloadSelector": {}
        }
    ]
}

def wait_pod(name, namespace="default"):
    podStatus=""
    while("Running" not in podStatus):
        cmd=f"kubectl get pods -l app={name} -n {namespace} "+ '--no-headers -o custom-columns=":status.phase"'
        podStatus =subprocess.check_output(cmd, shell=True).decode('utf-8')
        if ("Running" not in podStatus):
            time.sleep(1)
        else:
            break

def status_network(manager: Manager):
    namespace = manager.namespace
    cluster_name = manager.cluster_name
    try:
        # Check skupper status.
        check_status_command = SKUPPER_STATUS_CMD.format(cluster_name=cluster_name, namespace=namespace)
        status_output = subprocess.check_output(check_status_command, shell=True, timeout=10).decode('utf-8')
        if 'Skupper is not enabled' in status_output:
            return False
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print('Failed to check Skupper status. Check if Skupper is installed correctly.')
        raise e

def set_context(cluster: str):
    try:
        context_cmd = KUBE_CONTEXT_CMD.format(cluster_name=cluster)
        subprocess.check_output(context_cmd, shell=True, timeout=10).decode('utf-8')
    except (subprocess.CalledProcessError) as e:
        print('Failed to set context to cluster : {e.cmd}')
        raise e        
    
def get_clusterlink_gw_target(cluster: str):
    set_context(cluster)
    if cluster.startswith(KIND_PREFIX):
        clJson=json.loads(subprocess.getoutput('kubectl get nodes -o json'))
        ip = clJson["items"][0]["status"]["addresses"][0]["address"]
        return ip, DEFAULT_CL_PORT_KIND
    # Clouds in general support load balancer to assign external IP
    ip = subprocess.check_output('kubectl get svc -l app=cl-dataplane  -o jsonpath="{.items[0].status.loadBalancer.ingress[0].ip}"', shell=True).decode('utf-8')
    return ip, DEFAULT_CL_PORT

# createLoadBalancer creates load-balancer to external access. 
def expose_clusterlink(cluster: str, port="443"):
    try:
        # Testing purpose on KIND Cluster
        if cluster.startswith(KIND_PREFIX):
            subprocess.check_output("kubectl delete service cl-dataplane", shell=True).decode('utf-8')
            subprocess.check_output(f"kubectl create service nodeport cl-dataplane --tcp={port}:{port} --node-port=30443", shell=True).decode('utf-8')
            time.sleep(1)
            return
        # Cloud scenario will go through this
        gwIp=""
        subprocess.check_output(f"kubectl expose deployment cl-dataplane --name=cl-dataplane-load-balancer --port={port} --target-port={port} --type=LoadBalancer", shell=True).decode('utf-8')
        while gwIp =="":
            gwIp=subprocess.check_output('kubectl get svc -l app=cl-dataplane  -o jsonpath="{.items[0].status.loadBalancer.ingress[0].ip}", shell=True').decode('utf-8')
            time.sleep(1)
    except subprocess.CalledProcessError as e:
        print(f"Failed to create load balancer : {e.cmd}")
        raise e

def init_clusterlink_gateway(cluster: str):
    try:
        certca = os.path.join(CL_DIRECTORY, CERT)
        cert = os.path.join(CL_DIRECTORY, cluster, CERT)
        key = os.path.join(CL_DIRECTORY, cluster, KEY)
        gw_ip, gw_port = get_clusterlink_gw_target(cluster)

        cl_init_cmd = CL_INIT_CMD.format(cluster_name=cluster, cl_gw_ip=gw_ip, gw_port=gw_port, certca=certca, cert=cert, key=key)
        print(cl_init_cmd)
        subprocess.check_output(cl_init_cmd, shell=True).decode('utf-8')
        cl_policy_cmd = CL_POLICY_CMD.format(cluster_name=cluster, policy_file=os.path.join(CL_DIRECTORY, POLICY_FILE))
        subprocess.check_output(cl_policy_cmd, shell=True).decode('utf-8')
    except subprocess.CalledProcessError as e:
        print(f"Failed to install Clusterlink : {e.cmd}")
        raise e

def launch_network_fabric():
    try:
        path = shutil.which("cl-adm")
        os.makedirs(CL_DIRECTORY, exist_ok=True)
        if path is None:
            cl_install_cmd = CL_INSTALL_CMD.format(dir=CL_DIRECTORY)
            subprocess.check_output(cl_install_cmd, shell=True).decode('utf-8')
            current_path = os.environ.get('PATH')
            os.environ['PATH'] = f"{CL_INSTALL_DIR}:{current_path}"
            print(os.environ.get('PATH'))
        subprocess.check_output(CLA_FABRIC_CMD, shell=True, cwd=CL_DIRECTORY).decode('utf-8')
        policy_file = json.dumps(policy_allow_all, indent=2)
        with open(os.path.join(CL_DIRECTORY,POLICY_FILE), "w") as file:
            file.write(policy_file)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to install Clusterlink : {e.cmd}")
        raise e


def launch_network(manager: Manager):
    namespace = manager.namespace
    cluster_name = manager.cluster_name
    set_context(cluster_name)

    try:
        path = shutil.which("cl-adm")
        if path is None:
            launch_network_fabric() 
        cl_peer_command = CLA_PEER_CMD.format(cluster_name=cluster_name)
        cl_deploy_command = CL_DEPLOY_CMD.format(cluster_name=cluster_name)
        subprocess.check_output(cl_peer_command, shell=True, cwd=CL_DIRECTORY).decode('utf-8')
        subprocess.check_output(cl_deploy_command, shell=True, cwd=CL_DIRECTORY).decode('utf-8')
        wait_pod("cl-controlplane")
        wait_pod("cl-dataplane")
        expose_clusterlink(cluster_name)
        init_clusterlink_gateway(cluster_name)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to install Clusterlink on `{cluster_name}`: {e.cmd}")
        raise e
        
    
def check_link_status(source_cluster_name: str, target_cluster_name: str):
    status_link_command = CL_LINK_STATUS_CMD.format(cluster_name=source_cluster_name, peer=target_cluster_name)
    status_output = subprocess.getoutput(status_link_command)
    if f'Error' in status_output:
        return False
    return True

    
def create_link(link_name: str, source_manager: Manager, target_manager: Manager):
    source_namespace = source_manager.namespace
    source_cluster_name = source_manager.cluster_name

    target_namespace = target_manager.namespace
    target_cluster_name = target_manager.cluster_name
    if check_link_status(source_cluster_name, target_cluster_name):
        return

    try:
        source_cluster_ip,source_cluster_port = get_clusterlink_gw_target(source_cluster_name)
        target_cluster_ip,target_cluster_port = get_clusterlink_gw_target(target_cluster_name)
        create_link_command1 = CL_LINK_CMD.format(cluster_name=source_cluster_name, peer=target_cluster_name, target_ip=target_cluster_ip, target_port=target_cluster_port)
        create_link_command2 = CL_LINK_CMD.format(cluster_name=target_cluster_name, peer=source_cluster_name, target_ip=source_cluster_ip, target_port=source_cluster_port)
        subprocess.check_output(create_link_command1, shell=True).decode('utf-8')
        subprocess.check_output(create_link_command2, shell=True).decode('utf-8')
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print('Failed to establish a link between two clusters.')
        raise e


def delete_link(link_name: str, manager: Manager):
    namespace = manager.namespace
    cluster_name = manager.cluster_name

    if not check_link_status(link_name, manager):
        return
    try:
        delete_link_command= CL_LINK_DELETE_CMD.format(cluster_name=cluster_name, peer=link_name)
        subprocess.check_output(delete_link_command, shell=True).decode('utf-8')
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print('Failed delete a link between two clusters.')
        raise e


def export_service(service_name: str, manager: Manager, ports: List[int]):
    namespace = manager.namespace
    cluster_name = manager.cluster_name
    expose_service_name = f'{service_name}-{cluster_name}'
    try:
        for port in ports:
            export_cmd = CL_EXPORT_CMD.format(cluster_name=cluster_name, service_name=expose_service_name, service_target=service_name, port=port)
            subprocess.check_output(export_cmd, shell=True).decode('utf-8')
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print('Failed to expose service.')
        raise e

def import_service(service_name: str, manager: Manager, peer: str, ports: List[int]):
    namespace = manager.namespace
    cluster_name = manager.cluster_name
    import_service_name = f'{service_name}-{peer}'
    try:
        for port in ports:
            import_cmd = CL_IMPORT_CMD.format(cluster_name=cluster_name, service_name=import_service_name, port=port)
            bind_cmd = CL_BIND_CMD.format(cluster_name=cluster_name, service_name=import_service_name, peer=peer)
            subprocess.check_output(import_cmd, shell=True).decode('utf-8')
            subprocess.check_output(bind_cmd, shell=True).decode('utf-8')
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print('Failed to expose service.')
        raise e
    
def unexpose_service(service_name: str, manager: Manager):
    namespace = manager.namespace
    cluster_name = manager.cluster_name
    expose_service_name = f'{service_name}-{cluster_name}'
    unexpose_cmd = f'skupper unexpose service {service_name}.{namespace} --address {expose_service_name} --context {cluster_name} --namespace {namespace}'
    try:
        # Create authetnication token.
        subprocess.check_output(unexpose_cmd, shell=True).decode('utf-8')
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print('Failed to expose service.')
        raise e

    
