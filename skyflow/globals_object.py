"""
Globals contains variables used across the Skyflow.
This file is different from the globals.py file to avoid circular imports.
"""
from skyflow.templates import (Cluster, Endpoints, FilterPolicy, Job, Link,
                               Namespace, Role, Service)

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