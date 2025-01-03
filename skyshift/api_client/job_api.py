"""
JobAPI.
"""
import requests

from skyshift.api_client.object_api import NamespaceObjectAPI


class JobAPI(NamespaceObjectAPI):
    """
    Job API for handling Job objects.
    """

    def __init__(self, namespace: str = ""):
        super().__init__(namespace=namespace, object_type="jobs")

    def logs(self, name: str):
        """
        Get logs of a job.
        """
        response = requests.get(f"{self.url}/{name}/logs",
                                headers=self.auth_headers).json()
        return response
