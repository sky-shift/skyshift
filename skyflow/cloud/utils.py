"""
Utils for cloud functionality
"""
import os
import shutil

from skyflow.globals import SKYCONF_DIR


def skypilot_ssh_path(node_name: str):
    """Returns the path to the SSH key for the given SkyPilot node"""
    return os.path.expanduser("~/.sky/generated/ssh") + "/" + node_name

def cloud_cluster_dir(cluster_name: str):
    """Returns the path to the cloud cluster directory"""
    return os.path.join(SKYCONF_DIR, "clusters", cluster_name)

def delete_unused_cluster_config(cluster_name: str):
    """Deletes the cluster config directory from the Skyconf directory."""
    try:
        shutil.rmtree(cloud_cluster_dir(cluster_name))
    except FileNotFoundError:
        pass
