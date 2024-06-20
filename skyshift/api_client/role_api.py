"""
Role API.
"""
from skyshift.api_client.object_api import NoNamespaceObjectAPI


class RoleAPI(NoNamespaceObjectAPI):
    """
    Role API for handling Role objects.
    """

    def __init__(self):
        super().__init__(object_type='roles')
