"""
Object API.
"""
from urllib.parse import quote

import requests

from skyflow.utils import load_object, watch_events
from skyflow.utils.utils import load_manager_config


def verify_response(input_data):
    """
    Verifies API response or data to check for error.
    """
    if hasattr(input_data, 'status_code') and callable(
            getattr(input_data, 'json', None)):
        if input_data.status_code >= 400:
            try:
                body = input_data.json()
            except ValueError:  # In case the response body is not JSON
                body = {}
            error_msg = body.get(
                'detail',
                f'HTTP error occurred: Status code {input_data.status_code}')
            raise APIException(error_msg)
        body = input_data.json()
    else:
        # Assume input_data is already parsed data for non-Response inputs
        body = input_data
        if "detail" in body:
            raise APIException(body["detail"])

    return load_object(body)


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
        self.host, self.port = load_manager_config()
        self.object_type = object_type
        if namespace:
            self.url = f"http://{self.host}:{self.port}/{self.namespace}/{self.object_type}"
        else:
        if namespace:
            self.url = f"http://{self.host}:{self.port}/{self.namespace}/{self.object_type}"
        else:
            self.url = f"http://{self.host}:{self.port}/{self.object_type}"

    def create(self, config: dict):
        assert self.namespace, "Method `create` requires a namespace."
        assert self.namespace, "Method `create` requires a namespace."
        response = requests.post(self.url, json=config)
        return verify_response(response)

    def update(self, config: dict):
        assert self.namespace, "Method `update` requires a namespace."
        response = requests.put(self.url, json=config)
        assert self.namespace, "Method `update` requires a namespace."
        response = requests.put(self.url, json=config)
        return verify_response(response)

    def list(self):
        response = requests.get(self.url)
        response = requests.get(self.url)
        return verify_response(response)

    def get(self, name: str):
        assert self.namespace, "Method `get` requires a namespace."
        response = requests.get(f"{self.url}/{name}")
        return verify_response(response)

    def delete(self, name: str):
        assert self.namespace, "Method `delete` requires a namespace."
        response = requests.delete(f"{self.url}/{name}")
        return verify_response(response)

    def watch(self):
        watch_url = f"{self.url}?watch=true"
        for data in watch_events(watch_url):
            yield verify_response(data)


class NoNamespaceObjectAPI(ObjectAPI):
    """
    NoNamespace Object API - API for Sky-scoped objects.
    """

    def __init__(self, object_type: str):
        self.object_type = object_type
        self.host, self.port = load_manager_config()
        self.url = f"http://{self.host}:{self.port}/{self.object_type}"

    def create(self, config: dict):
        response = requests.post(self.url, json=config)
        return verify_response(response)
        response = requests.post(self.url, json=config)
        return verify_response(response)

    def update(self, config: dict):
        response = requests.put(self.url, json=config)
        return verify_response(response)
        response = requests.put(self.url, json=config)
        return verify_response(response)

    def list(self):
        response = requests.get(self.url)
        return verify_response(response)
        response = requests.get(self.url)
        return verify_response(response)

    def get(self, name: str):
        response = requests.get(f"{self.url}/{name}")
        return verify_response(response)

    def delete(self, name: str):
        response = requests.delete(f"{self.url}/{name}")
        return verify_response(response)

    def watch(self):
        for data in watch_events(f"{self.url}?watch=true"):
            yield verify_response(data)