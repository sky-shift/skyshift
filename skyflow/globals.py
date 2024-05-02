"""
Globals contains variables used across the Skyflow.
"""
import os

CLUSTER_TIMEOUT = 10 # seconds

USER_SSH_PATH = os.path.expanduser("~/.ssh")

SKYCONF_DIR = os.path.expanduser("~/.skyconf")

API_SERVER_CONFIG_PATH = "~/.skyconf/config.yaml"
SLURM_CONFIG_PATH = '~/.skyconf/slurmconf.yaml'
DEFAULT_NAMESPACE = "default"
KUBE_CONFIG_DEFAULT_PATH = "~/.kube/config"

KUBERNETES_ALIASES = ('kubernetes', 'k8', 'k8s')
KUBE_CONFIG_DEFAULT_PATH = '~/.kube/config'

SLURM_ALIASES = ('slurm', 'slurmctl')
SUPPORTED_MANAGERS = KUBERNETES_ALIASES + SLURM_ALIASES
SLURM_SUPPORTED_INTERFACES = ('rest', 'cli')


CLUSTER_TIMEOUT = 10  # seconds

def cluster_dir(cluster_name: str):
    """Returns the path to the cluster directory."""
    return os.path.join(SKYCONF_DIR, "cluster", cluster_name)
