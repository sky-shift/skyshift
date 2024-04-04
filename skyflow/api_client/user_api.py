"""
User API.
"""
import requests
from skyflow.api_client.object_api import NoNamespaceObjectAPI

class UserAPI(NoNamespaceObjectAPI):
    """
    Users API for handling User objects.
    """

    def __init__(self):
        super().__init__(object_type='users')

    def register_user(self, username: str, email: str, password: str):
        """
        Register the user
        """
        data = {
            "username": username,
            "email": email,
            "password": password
        }
        response = requests.post(f"http://{self.host}:{self.port}/register_user", json=data)
        return response
    
    def login_user(self, username: str, password: str):
        """
        Login the user
        """
        data = {
            "username": username,
            "password": password
        }
        response = requests.post(f"http://{self.host}:{self.port}/token", json=data).json()
        return response
    
