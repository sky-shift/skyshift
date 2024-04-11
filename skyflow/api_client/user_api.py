"""
User API.
"""
from typing import List

import requests

from skyflow.api_client.object_api import NoNamespaceObjectAPI


class UserAPI(NoNamespaceObjectAPI):
    """
    Users API for handling User objects.
    """

    def __init__(self):
        super().__init__(object_type='users')

    def register_user(self, username: str, email: str, password: str,
                      invite: str):
        """
        Send register API call.
        """
        data = {
            "user": {
                "username": username,
                "email": email,
                "password": password,
            },
            "invite_token": invite
        }
        response = requests.post(f"{self.base_url}/register_user", json=data)
        return response

    def login_user(self, username: str, password: str):
        """
        Send login API call.
        """
        data = {"username": username, "password": password}
        response = requests.post(f"{self.base_url}/token", data=data)
        return response

    def create_invite(self, roles: List[str] = []):
        """
        Send create invite API call.
        """
        data = {
            "roles": roles,
        }
        response = requests.post(f"{self.base_url}/invite",
                                 json=data,
                                 headers=self.auth_headers)
        return response