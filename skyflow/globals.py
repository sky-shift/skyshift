"""
Globals contains variables used across the Skyflow.
"""
from skyflow.templates import Job, FilterPolicy, Service, Endpoints, Cluster, Namespace, Link

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
