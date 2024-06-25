"""
Link API.
"""

from skyshift.api_client.object_api import NoNamespaceObjectAPI


class LinkAPI(NoNamespaceObjectAPI):
    """
    Link API for handling Link objects.
    """

    def __init__(self):
        super().__init__(object_type='links')
