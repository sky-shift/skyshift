# For now, we implement linking of clusters using Skupper.
import subprocess

from skyflow.cluster_manager import Manager

SKUPPER_INSTALL_CMD = 'skupper init --context {cluster_name} --namespace {namespace}'
SKUPPER_STATUS_CMD = 'skupper status --context {cluster_name} --namespace {namespace}'

SKUPPER_TOKEN_CMD = 'skupper token create ~/skym/link_secrets/{name}.token --context {cluster_name} --namespace {namespace}'

SKUPPER_LINK_CMD = 'skupper link create ~/skym/link_secrets/{name}.token --context {cluster_name} --namespace {namespace} --name {name}'

SKUPPER_DELETE_CMD = 'skupper delete link {name} --context {cluster_name} --namespace {namespace}'


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
    


def create_link(link_name: str, source_manager: Manager, target_manager: Manager):
    source_namespace = source_manager.namespace
    source_cluster_name = source_manager.cluster_name

    target_namespace = target_manager.namespace
    target_cluster_name = target_manager.cluster_name

    try:
        # Create authetnication token.
        create_token_command = SKUPPER_TOKEN_CMD.format(cluster_name=target_cluster_name, namespace=target_namespace)
        subprocess.check_output(create_token_command, shell=True, timeout=30).decode('utf-8')
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print('Failed generate a secret token with Skupper. Check if Skupper is installed correctly.')
        raise e

    try:
        # Create authetnication token.
        create_link_command= SKUPPER_LINK_CMD.format(cluster_name=source_cluster_name, namespace=source_namespace)
        subprocess.check_output(create_link_command, shell=True, timeout=30).decode('utf-8')
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print('Failed to establish a link between two clusters.')
        raise e
    


def delete_link(link_name: str, manager: Manager):
    namespace = manager.namespace
    cluster_name = manager.cluster_name

    try:
        # Create authetnication token.
        delete_link_command= SKUPPER_DELETE_CMD.format(cluster_name=cluster_name, namespace=namespace, name=link_name)
        subprocess.check_output(delete_link_command, shell=True, timeout=30).decode('utf-8')
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print('Failed delete a link between two clusters.')
        raise e