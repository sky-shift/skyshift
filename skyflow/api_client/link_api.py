from skyflow.api_client import NoNamespaceObjectAPI

class LinkAPI(NoNamespaceObjectAPI):

    def __init__(self):
        self.object_type = 'links'
        super().__init__()
