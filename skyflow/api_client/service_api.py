from skyflow.api_client import NamespaceObjectAPI
from skyflow.globals import DEFAULT_NAMESPACE

class ServiceAPI(NamespaceObjectAPI):

    def __init__(self, namespace: str = DEFAULT_NAMESPACE):
        self.object_type = 'services'
        super().__init__(namespace=namespace)