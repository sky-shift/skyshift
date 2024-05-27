"""
Globals contains variables used across the Skyflow.
"""
import os

CLUSTER_TIMEOUT = 10  # seconds

USER_SSH_PATH = os.path.expanduser("~/.ssh")

SKYCONF_DIR = os.path.expanduser("~/.skyconf")

API_SERVER_CONFIG_PATH = "~/.skyconf/config.yaml"

RAY_MANAGERS = ["ray"]
RAY_CLUSTERS_CONFIG_PATH = "~/.skyconf/ray.yaml"

DEFAULT_NAMESPACE = "default"

K8_MANAGERS = ('kubernetes', 'k8', 'k8s')
KUBE_CONFIG_DEFAULT_PATH = "~/.kube/config"

SLURM_MANAGERS = ('slurm', 'slurmctl')
SLURM_CONFIG_DEFAULT_PATH = '~/.skyconf/slurm_config.yaml'

SUPPORTED_MANAGERS = K8_MANAGERS + SLURM_MANAGERS

CLUSTER_TIMEOUT = 10  # seconds

APP_NAME = "Skyflow"


def cluster_dir(cluster_name: str):
    """Returns the path to the cluster directory."""
    return os.path.join(SKYCONF_DIR, "cluster", cluster_name)
