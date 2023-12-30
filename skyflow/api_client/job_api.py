from skyflow.api_client import NamespaceObjectAPI
from skyflow.globals import DEFAULT_NAMESPACE

class JobAPI(NamespaceObjectAPI):

    def __init__(self, namespace: str = DEFAULT_NAMESPACE):
        self.object_type = 'jobs'
        super().__init__(namespace=namespace)
