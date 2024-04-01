"""
Role API.
"""
from skyflow.api_client.object_api import NoNamespaceObjectAPI
from skyflow.api_client.api_client_exception import RuleAPIException

class RoleAPI(NoNamespaceObjectAPI):
    """
    Role API for handling Role objects.
    """

    def __init__(self):
        super().__init__(object_type='roles')
