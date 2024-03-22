"""
Globals contains variables used across the Skyflow.
"""
import os

from skyflow.templates import (Cluster, Endpoints, FilterPolicy, Job, Link,
                               Namespace, Role, Service)

USER_SSH_PATH = os.path.expanduser("~/.ssh")

SKYCONF_DIR = os.path.expanduser("~/.skyconf")

DEFAULT_NAMESPACE = "default"

NAMESPACED_OBJECTS = {
    "jobs": Job,
    "filterpolicies": FilterPolicy,
    "services": Service,
    "endpoints": Endpoints,
}
NON_NAMESPACED_OBJECTS = {
    "clusters": Cluster,
    "namespaces": Namespace,
    "links": Link,
    "roles": Role,
}
ALL_OBJECTS = {**NON_NAMESPACED_OBJECTS, **NAMESPACED_OBJECTS}

KUBERNETES_ALIASES = ('kubernetes', 'k8', 'k8s')
SLURM_ALIASES = ('slurm', 'slurmctl')
SUPPORTED_MANAGERS = KUBERNETES_ALIASES + SLURM_ALIASES

def cluster_dir(cluster_name: str):
    """Returns the path to the cluster directory."""
    return os.path.join(SKYCONF_DIR, "cluster", cluster_name)
