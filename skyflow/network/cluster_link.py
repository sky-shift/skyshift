# For now, we implement linking of clusters using Skupper.
import os
import subprocess
from typing import List

from skyflow.cluster_manager import Manager

TOKEN_DIRECTORY = '~/.skym/link_secrets'

SKUPPER_INSTALL_CMD = 'skupper init --context {cluster_name} --namespace {namespace}'
SKUPPER_STATUS_CMD = 'skupper status --context {cluster_name} --namespace {namespace}'
SKUPPER_TOKEN_CMD = 'skupper token create ~/.skym/link_secrets/{name}.token --context {cluster_name} --namespace {namespace}'
SKUPPER_LINK_CREATE_CMD = 'skupper link create ~/.skym/link_secrets/{name}.token --context {cluster_name} --namespace {namespace} --name {name}'
SKUPPER_LINK_DELETE_CMD = 'skupper link delete {name} --context {cluster_name} --namespace {namespace}'
SKUPPER_LINK_STATUS_CMD = 'skupper link status {name} --context {cluster_name} --namespace {namespace}'


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


def launch_network(manager: Manager):
    namespace = manager.namespace
    cluster_name = manager.cluster_name
    try:
        install_command = SKUPPER_INSTALL_CMD.format(cluster_name=cluster_name, namespace=namespace)
        subprocess.check_output(install_command, shell=True).decode('utf-8')
    except subprocess.CalledProcessError as e:
        print(f"Failed to install Skupper on `{cluster_name}`: {e.cmd}")
        raise e
    
def check_link_status(link_name: str, manager: Manager):
    namespace = manager.namespace
    cluster_name = manager.cluster_name
    
    try:
        status_link_command = SKUPPER_LINK_STATUS_CMD.format(name=link_name, cluster_name=cluster_name, namespace=namespace)
        status_output = subprocess.check_output(status_link_command, shell=True, timeout=10).decode('utf-8')
        if f'No such link' in status_output:
            return False
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print('Failed to check Skupper status. Check if Skupper is installed correctly.')
        raise e


def create_link(link_name: str, source_manager: Manager, target_manager: Manager):
    source_namespace = source_manager.namespace
    source_cluster_name = source_manager.cluster_name

    target_namespace = target_manager.namespace
    target_cluster_name = target_manager.cluster_name

    if check_link_status(link_name, source_manager):
        return

    try:
        # Create authetnication token.
        full_path = os.path.abspath(os.path.expanduser(TOKEN_DIRECTORY))
        os.makedirs(full_path, exist_ok=True)
        create_token_command = SKUPPER_TOKEN_CMD.format(name=link_name, cluster_name=target_cluster_name, namespace=target_namespace)
        subprocess.check_output(create_token_command, shell=True, timeout=30).decode('utf-8')
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print('Failed generate a secret token with Skupper. Check if Skupper is installed correctly.')
        raise e

    try:
        # Create a link between two clusters.
        create_link_command= SKUPPER_LINK_CREATE_CMD.format(name=link_name, cluster_name=source_cluster_name, namespace=source_namespace)
        subprocess.check_output(create_link_command, shell=True, timeout=30).decode('utf-8')
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print('Failed to establish a link between two clusters.')
        raise e
    


def delete_link(link_name: str, manager: Manager):
    namespace = manager.namespace
    cluster_name = manager.cluster_name

    if not check_link_status(link_name, manager):
        return
    try:
        # Delete authentication token.
        token_path = os.path.abspath(os.path.expanduser(TOKEN_DIRECTORY)) + '/' + link_name + '.token'
        os.remove(token_path)
        delete_link_command= SKUPPER_LINK_DELETE_CMD.format(name=link_name, cluster_name=cluster_name, namespace=namespace)
        subprocess.check_output(delete_link_command, shell=True, timeout=30).decode('utf-8')
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print('Failed delete a link between two clusters.')
        raise e


def expose_service(service_name: str, manager: Manager, ports: List[int]):
    namespace = manager.namespace
    cluster_name = manager.cluster_name
    expose_service_name = f'{service_name}-{cluster_name}'
    expose_cmd = f'skupper expose service {service_name}.{namespace} --address {expose_service_name} --context {cluster_name} --namespace {namespace} '
    for port in ports:
        expose_cmd += f'--port {port} --target-port {port} '
    try:
        subprocess.check_output(expose_cmd, shell=True, timeout=20).decode('utf-8')
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
        subprocess.check_output(unexpose_cmd, shell=True, timeout=20).decode('utf-8')
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print('Failed to expose service.')
        raise e

    
