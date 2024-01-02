from skyflow.templates import *
from skyflow.api_client import *

DEFAULT_NAMESPACE = 'default'

NAMESPACED_OBJECTS = {
    'jobs': Job,
    'filterpolicies': FilterPolicy,
    'services': Service,
    'endpoints': Endpoints,
}
NON_NAMESPACED_OBJECTS = {
    'clusters': Cluster,
    'namespaces': Namespace,
    'links': Link,
}
ALL_OBJECTS = {**NON_NAMESPACED_OBJECTS, **NAMESPACED_OBJECTS}

