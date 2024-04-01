"""
JobAPI.
"""
import requests

from skyflow.api_client.object_api import NamespaceObjectAPI
from skyflow.globals import DEFAULT_NAMESPACE
from skyflow.api_client.api_client_exception import JobAPIException


class JobAPI(NamespaceObjectAPI):
    """
    Job API for handling Job objects.
    """

    def __init__(self, namespace: str = DEFAULT_NAMESPACE):
        super().__init__(namespace=namespace, object_type="jobs")

    def logs(self, name: str):
        """
        Get logs of a Job.
        """
        response = requests.get(f"{self.url}/{name}/logs").json()
        return response
