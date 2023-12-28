# For now, we implement linking of clusters using Skupper.
import subprocess

from sky_manager.cluster_manager import Manager

SKUPPER_INSTALL_CMD = 'skupper init --context {cluster_name} --namespace {namespace}'
SKUPPER_STATUS_CMD = 'skupper status --context {cluster_name} --namespace {namespace}'


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
    
