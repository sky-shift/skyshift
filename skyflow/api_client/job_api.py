"""
JobAPI.
"""
from skyflow.api_client.object_api import NamespaceObjectAPI
from skyflow.globals import DEFAULT_NAMESPACE


class JobAPI(NamespaceObjectAPI):
    """
    Job API for handling Job objects.
    """

    def __init__(self, namespace: str = DEFAULT_NAMESPACE):
        super().__init__(namespace=namespace, object_type="jobs")
