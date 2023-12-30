from skyflow.api_client import NoNamespaceObjectAPI


class NamespaceAPI(NoNamespaceObjectAPI):

    def __init__(self):
        self.object_type = 'namespaces'
        super().__init__()
