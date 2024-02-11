"""
Globals contains variables used across the Skyflow.
"""
from skyflow.templates import (Cluster, Endpoints, FilterPolicy, Job, Link,
                               Namespace, Service)

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
}
ALL_OBJECTS = {**NON_NAMESPACED_OBJECTS, **NAMESPACED_OBJECTS}

KUBERNETES_ALIASES = ("kubernetes". "k8", "k8s")
SLURM_ALIASES = ("slurm", "slurmctl")
SUPPORTED_MANAGERS = KUBERNETES_ALIASES + SLURM_ALIASES
