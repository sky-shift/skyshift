"""
Namespace API.
"""
from skyflow.api_client.object_api import NoNamespaceObjectAPI


class NamespaceAPI(NoNamespaceObjectAPI):
    """
    Namespace API for handling Namespace objects.
    """

    def __init__(self):
        super().__init__(object_type='namespaces')
