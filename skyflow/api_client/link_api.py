"""
Link API.
"""

from skyflow.api_client.object_api import NoNamespaceObjectAPI
from skyflow.api_client.api_client_exception import LinkAPIException


class LinkAPI(NoNamespaceObjectAPI):
    """
    Link API for handling Link objects.
    """

    def __init__(self):
        super().__init__(object_type='links')
