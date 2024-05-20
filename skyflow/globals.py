"""
Globals contains variables used across the Skyflow.
"""
import os

USER_SSH_PATH = os.path.expanduser("~/.ssh")

SKYCONF_DIR = os.path.expanduser("~/.skyconf")

API_SERVER_CONFIG_PATH = "~/.skyconf/config.yaml"

DEFAULT_NAMESPACE = "default"

KUBE_CONFIG_DEFAULT_PATH = '~/.kube/config'

CLUSTER_TIMEOUT = 10  # seconds

APP_NAME = "SkyShift"


def cluster_dir(cluster_name: str):
    """Returns the path to the cluster directory."""
    return os.path.join(SKYCONF_DIR, "cluster", cluster_name)
