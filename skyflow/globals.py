"""
Globals contains variables used across the Skyflow.
"""
import os

from skyflow.templates import (Cluster, Endpoints, FilterPolicy, Job, Link,
                               Namespace, Role, Service, User)

USER_SSH_PATH = os.path.expanduser("~/.ssh")

SKYCONF_DIR = os.path.expanduser("~/.skyconf")

API_SERVER_CONFIG_PATH = "~/.skyconf/config.yaml"

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
    "users": User,
}
ALL_OBJECTS = {**NON_NAMESPACED_OBJECTS, **NAMESPACED_OBJECTS}


def cluster_dir(cluster_name: str):
    """Returns the path to the cluster directory."""
    return os.path.join(SKYCONF_DIR, "cluster", cluster_name)
