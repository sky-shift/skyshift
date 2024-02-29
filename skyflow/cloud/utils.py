"""
Utils for cloud functionality
"""
import os

from skyflow.globals import SKYCONF_DIR


def skypilot_ssh_path(node_name: str):
    """Returns the path to the SSH key for the given SkyPilot node"""
    return os.path.expanduser("~/.sky/generated/ssh") + "/" + node_name


def cloud_cluster_dir(cluster_name: str):
    """Returns the path to the cloud cluster directory"""
    return SKYCONF_DIR + "/" + cluster_name
