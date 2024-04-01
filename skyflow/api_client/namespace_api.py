"""
Namespace API.
"""
from skyflow.api_client.object_api import NoNamespaceObjectAPI
from skyflow.api_client.api_client_exception import NamespaceAPIException


class NamespaceAPI(NoNamespaceObjectAPI):
    """
    Namespace API for handling Namespace objects.
    """

    def __init__(self):
        super().__init__(object_type='namespaces')
