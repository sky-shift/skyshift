from skyflow.api_client.object_api import NoNamespaceObjectAPI


class LinkAPI(NoNamespaceObjectAPI):

    def __init__(self):
        self.object_type = 'links'
        super().__init__()
