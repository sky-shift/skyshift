import requests

from sky_manager import utils

from sky_manager.api_server.api_server import load_manager_config


def _verify_response(response):
    if 'error' in response:
        raise Exception(response['error'])


class NamespaceAPI(object):

    def __init__(self):
        self.host, self.port = load_manager_config()
        self.namespace_url = f'http://{self.host}:{self.port}/namespaces'

    def Create(self, config: dict):
        response = requests.post(self.namespace_url, json=config).json()
        _verify_response(response)
        return response

    def Update(self, config: dict):
        response = requests.put(self.namespace_url, json=config).json()
        _verify_response(response)
        return response

    def List(self):
        response = requests.get(self.namespace_url).json()
        _verify_response(response)
        return response

    def Get(self, namespace: str):
        response = requests.get(f'{self.namespace_url}/{namespace}').json()
        _verify_response(response)
        return response

    def Delete(self, namespace: str):
        response = requests.delete(f'{self.namespace_url}/{namespace}').json()
        _verify_response(response)
        return response

    def Watch(self):
        for data in utils.watch_events(f'{self.namespace_url}?watch=true'):
            yield data
