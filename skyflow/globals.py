"""
Globals contains variables used across the Skyflow.
"""
import os

USER_SSH_PATH = os.path.expanduser("~/.ssh")

SKYCONF_DIR = os.path.expanduser("~/.skyconf")

API_SERVER_CONFIG_PATH = "~/.skyconf/config.yaml"

API_SERVER_CONFIG_PATH = "~/.skyconf/config.yaml"

DEFAULT_NAMESPACE = "default"


def cluster_dir(cluster_name: str):
    """Returns the path to the cluster directory."""
    return os.path.join(SKYCONF_DIR, "cluster", cluster_name)
