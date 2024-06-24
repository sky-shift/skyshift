"""
Utils for cloud functionality
"""
import os
import shutil

import paramiko
import scp

from skyshift.globals import SKYCONF_DIR, SKYPILOT_SSH_PATH
from skyshift.utils.scp_utils import create_scp_client
from skyshift.utils.ssh_utils import read_and_connect_from_config

# See here for details: https://rke.docs.rancher.com/os#ports
RKE_PORTS = [
    "9345",  # Listen for new nodes
    "22",
    "6443",
    "2376",
    "2379",
    "2380",
    "8472",
    "9099",
    "10250",
    "443",
    "379",
    "6443",
    "8472",
    "80",
    "472",
    "10254",
    "3389",
    "30000-32767",
    "7946",
    "179",
    "6783-6784",
    "9796",
    "9443",
    "9100",
    "8443",
    "4789",
]


def parse_ssh_config(node_name: str) -> str:
    """
    Parse the SSH config file and return the HostName.
    """
    with open(skypilot_ssh_path(node_name), 'r') as file:
        lines = file.readlines()

    for line in lines:
        line = line.strip()
        if line.startswith('HostName '):
            return line.split()[1]

    # If no HostName is found, throw an error
    raise ValueError("No HostName found in SSH config file.")


def skypilot_ssh_path(node_name: str):
    """Returns the path to the SSH key for the given SkyPilot node"""
    return os.path.join(SKYPILOT_SSH_PATH, node_name)


def cloud_cluster_dir(cluster_name: str):
    """Returns the path to the cloud cluster directory"""
    return os.path.join(SKYCONF_DIR, "clusters", cluster_name)


def delete_unused_cluster_config(cluster_name: str):
    """Deletes the cluster config directory from the Skyconf directory."""
    try:
        shutil.rmtree(cloud_cluster_dir(cluster_name))
    except FileNotFoundError:
        pass


def create_ssh_scp_clients(
        skypilot_node: str) -> tuple[paramiko.SSHClient, scp.SCPClient]:
    """Create SSH and SCP client using the host information."""
    ssh_path = skypilot_ssh_path(skypilot_node)
    ssh_client = read_and_connect_from_config(skypilot_node, ssh_path)
    scp_client = create_scp_client(ssh_client)
    return (ssh_client, scp_client)
