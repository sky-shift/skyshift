from skyflow.api_client.object_api import NoNamespaceObjectAPI


class ClusterAPI(NoNamespaceObjectAPI):

    def __init__(self):
        self.object_type = 'clusters'
        super().__init__()
