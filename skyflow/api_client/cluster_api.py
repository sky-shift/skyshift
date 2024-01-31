"""
Cluster API.
"""
from skyflow.api_client.object_api import NoNamespaceObjectAPI


class ClusterAPI(NoNamespaceObjectAPI):
    """
    Cluster API for handling Cluster objects.
    """

    def __init__(self):
        super().__init__(object_type='clusters')
