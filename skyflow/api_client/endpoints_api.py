"""
Endpoints API (Internal Use only).
"""
from skyflow.api_client.object_api import NamespaceObjectAPI
from skyflow.globals import DEFAULT_NAMESPACE
from skyflow.api_client.api_client_exception import EndpointAPIException


class EndpointsAPI(NamespaceObjectAPI):
    """
    Endpoints API for handling Endpoints objects.
    """

    def __init__(self, namespace: str = DEFAULT_NAMESPACE):
        super().__init__(namespace=namespace, object_type="endpoints")
