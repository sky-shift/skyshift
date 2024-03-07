"""
Globals contains variables used across the Skyflow.
"""
import os

from skyflow.templates import (Cluster, Endpoints, FilterPolicy, Job, Link,
                               Namespace, Role, Service)

DEFAULT_NAMESPACE = "default"

USER_SSH_PATH = os.path.expanduser("~/.ssh")

SKYCONF_DIR = os.path.expanduser("~/.skyconf")

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
