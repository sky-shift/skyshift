"""
Endpoints API (Internal Use only).
"""
from skyshift.api_client.object_api import NamespaceObjectAPI


class EndpointsAPI(NamespaceObjectAPI):
    """
    Endpoints API for handling Endpoints objects.
    """

    def __init__(self, namespace: str = ""):
        super().__init__(namespace=namespace, object_type="endpoints")
