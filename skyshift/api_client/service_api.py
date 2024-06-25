"""
Service API.
"""

from skyshift.api_client.object_api import NamespaceObjectAPI


class ServiceAPI(NamespaceObjectAPI):
    """
    Service API for handling Service objects.
    """

    def __init__(self, namespace: str = ""):
        super().__init__(namespace=namespace, object_type="services")
