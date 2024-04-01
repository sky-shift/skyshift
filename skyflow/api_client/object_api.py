"""
Object API.
"""
import requests

from skyflow.utils import load_object, watch_events
from skyflow.utils.utils import load_manager_config
from skyflow.api_client.api_client_exception import APIResponseException, TokenNotFoundException, NamespaceObjectAPIException, NoNamespaceObjectAPIException
from skyflow.tests.test_exception import NoJsonDataError


def verify_response(input_data):
    """
    Verifies API response or data to check for error.
    """
    if hasattr(input_data, 'status_code') and callable(
            getattr(input_data, 'json', None)):
        if input_data.status_code >= 300:
            try:
                body = input_data.json()
            except NoJsonDataError:  # In case the response body is not JSON
                body = {}
            error_msg = body.get(
                'detail',
                f'HTTP error occurred: Status code {input_data.status_code}')
            raise APIResponseException(error_msg, input_data.status_code)
        body = input_data.json()
    else:
        # Assume input_data is already parsed data for non-Response inputs
        body = input_data
        if "detail" in body:
            APIResponseException(body["detail"], input_data.status_code)

    return load_object(body)


def fetch_auth_token(admin_config: dict) -> str:
    """Fetches the auth token from the Skyflow config."""
    target_user = admin_config.get('current_user', None)
    users = admin_config.get('users', [])
    if not users:
        raise TokenNotFoundException("No user found in config file", status_code=404)
    if target_user:
        for user in users:
            user_name = user.get('name', None)
            if user_name == target_user:
                return user['access_token']
        raise TokenNotFoundException(f"User {target_user} not found in config file", status_code=404)
    return users[0]['access_token']


class ObjectAPI:
    """
    Generic Object API.
    """

    def create(self, config: dict):
        """Creates an object."""
        raise NotImplementedError

    def update(self, config: dict):
        """Updates an object."""
        raise NotImplementedError

    def list(self):
        """Lists all objects."""
        raise NotImplementedError

    def get(self, name: str):
        """Gets an object."""
        raise NotImplementedError

    def delete(self, name: str):
        """Deletes an object."""
        raise NotImplementedError

    def watch(self):
        """Watches for changes to objects."""
        raise NotImplementedError


class NamespaceObjectAPI(ObjectAPI):
    """
    Namespaced Object API - API for namespace objects.
    """

    def __init__(self, namespace: str, object_type: str):
        self.namespace = namespace
        admin_config = load_manager_config()
        self.host = admin_config["api_server"]["host"]
        self.port = admin_config["api_server"]["port"]

        self.object_type = object_type
        if namespace:
            self.url = f"http://{self.host}:{self.port}/{self.namespace}/{self.object_type}"
        else:
            self.url = f"http://{self.host}:{self.port}/{self.object_type}"

        self.auth_headers = {
            "Authorization": f"Bearer {fetch_auth_token(admin_config)}"
        }

    def create(self, config: dict):
        assert self.namespace, "Method `create` requires a namespace."
        response = requests.post(self.url,
                                 json=config,
                                 headers=self.auth_headers)
        return verify_response(response)

    def update(self, config: dict):
        assert self.namespace, "Method `update` requires a namespace."
        response = requests.put(self.url,
                                json=config,
                                headers=self.auth_headers)
        return verify_response(response)

    def list(self):
        response = requests.get(self.url, headers=self.auth_headers)
        return verify_response(response)

    def get(self, name: str):
        assert self.namespace, "Method `get` requires a namespace."
        response = requests.get(f"{self.url}/{name}",
                                headers=self.auth_headers)
        return verify_response(response)

    def delete(self, name: str):
        assert self.namespace, "Method `delete` requires a namespace."
        response = requests.delete(f"{self.url}/{name}",
                                   headers=self.auth_headers)
        return verify_response(response)

    def watch(self):
        watch_url = f"{self.url}?watch=true"
        for data in watch_events(watch_url, headers=self.auth_headers):
            yield verify_response(data)


class NoNamespaceObjectAPI(ObjectAPI):
    """
    NoNamespace Object API - API for Sky-scoped objects.
    """

    def __init__(self, object_type: str):
        self.object_type = object_type
        admin_config = load_manager_config()
        self.host = admin_config["api_server"]["host"]
        self.port = admin_config["api_server"]["port"]
        self.url = f"http://{self.host}:{self.port}/{self.object_type}"
        self.auth_headers = {
            "Authorization": f"Bearer {fetch_auth_token(admin_config)}"
        }

    def create(self, config: dict):
        response = requests.post(self.url,
                                 json=config,
                                 headers=self.auth_headers)
        return verify_response(response)

    def update(self, config: dict):
        response = requests.put(self.url,
                                json=config,
                                headers=self.auth_headers)
        return verify_response(response)

    def list(self):
        response = requests.get(self.url, headers=self.auth_headers)
        return verify_response(response)

    def get(self, name: str):
        response = requests.get(f"{self.url}/{name}",
                                headers=self.auth_headers)
        return verify_response(response)

    def delete(self, name: str):
        response = requests.delete(f"{self.url}/{name}",
                                   headers=self.auth_headers)
        return verify_response(response)

    def watch(self):
        for data in watch_events(f"{self.url}?watch=true",
                                 headers=self.auth_headers):
            yield verify_response(data)
