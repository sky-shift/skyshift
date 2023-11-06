import requests

from sky_manager.api_server.api_server import load_manager_config
from sky_manager import utils


def _verify_response(response):
    if 'error' in response:
        raise Exception(response['error'])


class ClusterAPI(object):

    def __init__(self):
        self.host, self.port = load_manager_config()
        self.cluster_url = f'http://{self.host}:{self.port}/clusters'

    def Create(self, config: dict):
        response = requests.post(self.cluster_url, json=config).json()
        _verify_response(response)
        return response

    def Update(self, config: dict):
        response = requests.put(self.cluster_url, json=config).json()
        _verify_response(response)
        return response

    def List(self):
        response = requests.get(self.cluster_url).json()
        _verify_response(response)
        return response

    def Get(self, cluster: str):
        response = requests.get(f'{self.cluster_url}/{cluster}').json()
        _verify_response(response)
        return response

    def Delete(self, cluster: str):
        response = requests.delete(f'{self.cluster_url}/{cluster}').json()
        _verify_response(response)
        return response

    def Watch(self):
        for data in utils.watch_events(f'{self.cluster_url}?watch=true'):
            yield data