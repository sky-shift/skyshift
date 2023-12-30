import requests

from skyflow.utils.utils import load_manager_config
from skyflow.utils import load_object, watch_events


def verify_response(response):
    if 'detail' in response:
        raise APIException(response['detail'])
    return load_object(response)

class APIException(Exception):
    pass

class NamespaceObjectAPI(object):

    def __init__(self, namespace: str):
        self.namespace = namespace
        self.host, self.port = load_manager_config()
        if not self.object_type:
            raise NotImplementedError('Classes that inherit from this class must set the `object_type` attribute.')
        if namespace is None:
            self.url = f'http://{self.host}:{self.port}/{self.object_type}'
        else:
            self.url = f'http://{self.host}:{self.port}/{self.namespace}/{self.object_type}'


    def create(self, config: dict):
        assert self.namespace is not None, 'Method `create` requires a namespace.'
        response = requests.post(self.url, json=config)
        response = response.json()
        return verify_response(response)

    def update(self, config: dict):
        assert self.namespace is not None, 'Method `update` requires a namespace.'
        response = requests.put(self.url,
                                json=config).json()
        return verify_response(response)

    def list(self):
        response = requests.get(self.url).json()
        return verify_response(response)

    def get(self, name: str):
        assert self.namespace is not None, 'Method `get` requires a namespace.'
        response = requests.get(f'{self.url}/{name}').json()
        return verify_response(response)

    def delete(self, name: str):
        assert self.namespace is not None, 'Method `delete` requires namespace.'
        response = requests.delete(f'{self.url}/{name}').json()
        return verify_response(response)

    def watch(self):
        watch_url = f'{self.url}?watch=true'
        for data in watch_events(watch_url):
            yield verify_response(data)

class NoNamespaceObjectAPI(object):

    def __init__(self):
        self.host, self.port = load_manager_config()
        self.url = None
        # For classes that inherit from this class, they must set the object_type.
        if not self.object_type:
            raise NotImplementedError('Classes that inherit from this class must set the `object_type` attribute.')
        self.url = f'http://{self.host}:{self.port}/{self.object_type}'


    def create(self, config: dict):
        response = requests.post(self.url, json=config).json()
        obj = verify_response(response)
        return obj

    def update(self, config: dict):
        response = requests.put(self.url, json=config).json()
        obj = verify_response(response)
        return obj

    def list(self):
        response = requests.get(self.url).json()
        obj = verify_response(response)
        return obj

    def get(self, name: str):
        response = requests.get(f'{self.url}/{name}').json()
        obj = verify_response(response)
        return obj

    def delete(self, name: str):
        response = requests.delete(f'{self.url}/{name}').json()
        obj = verify_response(response)
        return obj

    def watch(self):
        for data in watch_events(f'{self.url}?watch=true'):
            yield verify_response(data)