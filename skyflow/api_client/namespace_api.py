from skyflow.api_client.object_api import NoNamespaceObjectAPI


class NamespaceAPI(NoNamespaceObjectAPI):

    def __init__(self):
        self.object_type = 'namespaces'
        super().__init__()
