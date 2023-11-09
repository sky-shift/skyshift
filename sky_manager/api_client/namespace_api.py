import requests

from sky_manager.api_client.object_api import ObjectAPI
from sky_manager.utils import utils

def _verify_response(response):
    if 'error' in response:
        raise Exception(response['error'])


class NamespaceAPI(ObjectAPI):

    def __init__(self):
        super().__init__()
        self.namespace_url = f'http://{self.host}:{self.port}/namespaces'

    def create(self, config: dict):
        response = requests.post(self.namespace_url, json=config).json()
        _verify_response(response)
        return response

    def update(self, config: dict):
        response = requests.put(self.namespace_url, json=config).json()
        _verify_response(response)
        return response

    def list(self):
        response = requests.get(self.namespace_url).json()
        _verify_response(response)
        return response

    def get(self, name: str):
        response = requests.get(f'{self.namespace_url}/{name}').json()
        _verify_response(response)
        return response

    def delete(self, name: str):
        response = requests.delete(f'{self.namespace_url}/{name}').json()
        _verify_response(response)
        return response

    def watch(self):
        for data in utils.watch_events(f'{self.namespace_url}?watch=true'):
            yield data
