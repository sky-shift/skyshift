"""
Cluster API.
"""
import requests
from skyflow import utils
from skyflow.api_client.object_api import NoNamespaceObjectAPI, verify_response


class ClusterAPI(NoNamespaceObjectAPI):
    """
    Cluster API for handling Cluster objects.
    """

    def __init__(self):
        super().__init__(object_type='clusters')
    
    def get(self, name: str):
        """
        Overrides the get method to sanitize the cluster name.
        """
        name = utils.sanitize_cluster_name(name)
        response = requests.get(f"{self.url}/{name}",
                                headers=self.auth_headers)
        return verify_response(response)

    def delete(self, name: str):
        """
        Overrides the delete method to sanitize the cluster name.
        """
        name = utils.sanitize_cluster_name(name)
        response = requests.delete(f"{self.url}/{name}",
                                   headers=self.auth_headers)
        return verify_response(response)
