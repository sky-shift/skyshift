from skyflow.api_client import NoNamespaceObjectAPI

class ClusterAPI(NoNamespaceObjectAPI):

    def __init__(self):
        self.object_type = 'clusters'
        super().__init__()
