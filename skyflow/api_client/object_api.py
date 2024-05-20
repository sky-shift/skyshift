"""
Object API.
"""
import requests

from skyflow.utils import load_object, watch_events
from skyflow.utils.utils import load_manager_config


def verify_response(input_data):
    """
    Verifies API response or data to check for error.
    """
    if hasattr(input_data, 'status_code') and callable(
            getattr(input_data, 'json', None)):
        if input_data.status_code >= 300:
            try:
                body = input_data.json()
            except ValueError:  # In case the response body is not JSON
                body = {}
            error_msg = body.get(
                'detail',
                f'HTTP error occurred: Status code {input_data.status_code}')
            raise APIException(input_data.status_code, error_msg)
        body = input_data.json()
    else:
        # Assume input_data is already parsed data for non-Response inputs
        body = input_data
        if "detail" in body:
            raise APIException(input_data.status_code, body["detail"])

    return load_object(body)


def fetch_context(admin_config: dict) -> str:
    """Fetches the context from the admin config."""
    target_context = admin_config.get('current_context', None)
    users = admin_config.get('users', [])
    if not users:
        raise APIException("No user found in config file")
    if not target_context:
        raise APIException("No current context found in config file.")
    
    found_context = None
    for context in admin_config.get('contexts', []):
        context_name = context.get('name', None)
        if context_name == target_context:
            found_context = context
            break
    if not found_context:
        raise APIException(f"Context {target_context} not found in config file")
    
    context_user = found_context.get('user', None)
    if not context_user:
        raise APIException(f"No user found in context {target_context}")
    if 'namespace' not in found_context:
        raise APIException(f"No namespace found in context {target_context}")
    
    for user in users:
        if user['name'] == context_user:
            found_context['access_token'] = user['access_token']
    return found_context


# @TODO(mluo): Introduce different types of API exceptions.
class APIException(Exception):
    """Generic API Exception."""


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

    def websocket_stream(self, config: dict):
        """Websocket stream for bidirectional communication."""
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
        
        context = fetch_context(admin_config)
        if not self.namespace:
            self.namespace = context["namespace"]
        access_token = context['access_token']

        self.object_type = object_type
        if namespace:
            self.url = f"http://{self.host}:{self.port}/{self.namespace}/{self.object_type}"
        else:
            self.url = f"http://{self.host}:{self.port}/{self.object_type}"

        self.auth_headers = {
            "Authorization": f"Bearer {access_token}"
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

    def websocket_stream(self, config: dict):
        """Websocket stream for bidirectional communication."""
        print("WebSocket stream does not have a default implementation.")

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
        self.base_url = f"http://{self.host}:{self.port}"
        self.url = f"{self.base_url}/{self.object_type}"
        
        context = fetch_context(admin_config)
        access_token = context["access_token"]
        self.auth_headers = {
            "Authorization": f"Bearer {access_token}"
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

    def websocket_stream(self, config: dict):
        print("WebSocket stream not implemented for this object type.")

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
            if not data:
                raise APIException("Watch unexpectedly terminated.")
            yield verify_response(data)
