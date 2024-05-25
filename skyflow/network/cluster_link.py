"""
Module to manage Skupper network operations.

@TODO(pravein): Convert to ClusterLink.
"""

import os
import subprocess
from typing import List

from skyflow.cluster_manager import KubernetesManager

TOKEN_DIRECTORY = "~/.skyconf/link_secrets"
INSTALL_CMD = ("skupper init --context {cluster_name} "
               "--namespace {namespace}")
STATUS_CMD = ("skupper status --context {cluster_name} "
              "--namespace {namespace}")
TOKEN_CMD = ("skupper token create ~/.skyconf/link_secrets/{name}.token "
             "--context {cluster_name} --namespace {namespace}")
LINK_CREATE_CMD = (
    "skupper link create ~/.skyconf/link_secrets/{name}.token "
    "--context {cluster_name} --namespace {namespace} --name {name}")
LINK_DELETE_CMD = (
    "skupper link delete {name} --context {cluster_name} --namespace {namespace}"
)
LINK_STATUS_CMD = (
    "skupper link status {name} --context {cluster_name} --namespace {namespace}"
)


def status_network(manager: KubernetesManager):
    """Checks if a Skupper router is running on a cluster."""
    namespace = manager.namespace
    cluster_name = manager.cluster_name
    try:
        # Check skupper status.
        check_status_command = STATUS_CMD.format(cluster_name=cluster_name,
                                                 namespace=namespace)
        status_output = subprocess.check_output(check_status_command,
                                                shell=True,
                                                timeout=10).decode("utf-8")
        if "Skupper is not enabled" in status_output:
            return False
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        print(
            "Failed to check Skupper status. Check if Skupper is installed correctly."
        )
        raise error


def launch_network(manager: KubernetesManager):
    """Launches a Skupper router on a cluster."""
    namespace = manager.namespace
    cluster_name = manager.cluster_name
    try:
        install_command = INSTALL_CMD.format(cluster_name=cluster_name,
                                             namespace=namespace)
        subprocess.check_output(install_command, shell=True).decode("utf-8")
    except subprocess.CalledProcessError as error:
        print(f"Failed to install Skupper on `{cluster_name}`.")
        raise error


def check_link_status(link_name: str, manager: KubernetesManager):
    """Checks if a link exists between two clusters."""
    namespace = manager.namespace
    cluster_name = manager.cluster_name

    try:
        status_link_command = LINK_STATUS_CMD.format(name=link_name,
                                                     cluster_name=cluster_name,
                                                     namespace=namespace)
        status_output = subprocess.check_output(status_link_command,
                                                shell=True,
                                                timeout=10).decode("utf-8")
        if "No such link" in status_output:
            return False
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        print(
            "Failed to check Skupper status. Check if Skupper is installed correctly."
        )
        raise error


def create_link(link_name: str, source_manager: KubernetesManager,
                target_manager: KubernetesManager):
    """Creates a link between two clusters."""
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
        create_token_command = TOKEN_CMD.format(
            name=link_name,
            cluster_name=target_cluster_name,
            namespace=target_namespace)
        subprocess.check_output(create_token_command, shell=True,
                                timeout=30).decode("utf-8")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        print(
            "Failed generate a secret token with Skupper. Check if Skupper is installed correctly."
        )
        raise error

    try:
        # Create a link between two clusters.
        create_link_command = LINK_CREATE_CMD.format(
            name=link_name,
            cluster_name=source_cluster_name,
            namespace=source_namespace)
        subprocess.check_output(create_link_command, shell=True,
                                timeout=30).decode("utf-8")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        print("Failed to establish a link between two clusters.")
        raise error


def delete_link(link_name: str, manager: KubernetesManager):
    """Deletes a link between two clusters."""
    namespace = manager.namespace
    cluster_name = manager.cluster_name

    if not check_link_status(link_name, manager):
        return
    try:
        # Delete authentication token.
        token_path = (os.path.abspath(os.path.expanduser(TOKEN_DIRECTORY)) +
                      "/" + link_name + ".token")
        os.remove(token_path)
        delete_link_command = LINK_DELETE_CMD.format(name=link_name,
                                                     cluster_name=cluster_name,
                                                     namespace=namespace)
        subprocess.check_output(delete_link_command, shell=True,
                                timeout=30).decode("utf-8")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        print("Failed delete a link between two clusters.")
        raise error


def expose_service(service_name: str, manager: KubernetesManager,
                   ports: List[int]):
    """Exposes a service on the Skupper network."""
    namespace = manager.namespace
    cluster_name = manager.cluster_name
    expose_service_name = f"{service_name}-{cluster_name}"
    expose_cmd = (f"skupper expose service {service_name}.{namespace} "
                  f"--address {expose_service_name} --context {cluster_name} "
                  f"--namespace {namespace} ")
    for port in ports:
        expose_cmd += f"--port {port} --target-port {port} "
    try:
        subprocess.check_output(expose_cmd, shell=True,
                                timeout=20).decode("utf-8")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        print("Failed to expose service.")
        raise error


def unexpose_service(service_name: str, manager: KubernetesManager):
    """Removes the exposed service from the Skupper network."""
    namespace = manager.namespace
    cluster_name = manager.cluster_name
    expose_service_name = f"{service_name}-{cluster_name}"
    unexpose_cmd = (f"skupper unexpose service {service_name}.{namespace} "
                    f"--address {expose_service_name} "
                    f"--context {cluster_name} "
                    f"--namespace {namespace}")
    try:
        # Create authentication token.
        subprocess.check_output(unexpose_cmd, shell=True,
                                timeout=20).decode("utf-8")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        print("Failed to expose service.")
        raise error
