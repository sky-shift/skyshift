"""
FilterPolicy API.
"""
from skyflow.api_client.object_api import NamespaceObjectAPI


class FilterPolicyAPI(NamespaceObjectAPI):
    """
    FilterPolicy API for handling FilterPolicy objects.
    """

    def __init__(self, namespace: str = None):
        super().__init__(namespace=namespace, object_type="filterpolicies")
