import requests

from sky_manager.api_client import ObjectAPI
from sky_manager.utils import utils

def _verify_response(response):
    if 'detail' in response:
        raise Exception(response['detail'])

class ClusterAPI(ObjectAPI):

    def __init__(self):
        super().__init__()
        self.cluster_url = f'http://{self.host}:{self.port}/clusters'

    def create(self, config: dict):
        response = requests.post(self.cluster_url, json=config).json()
        _verify_response(response)
        return response

    def update(self, config: dict):
        response = requests.put(self.cluster_url, json=config).json()
        _verify_response(response)
        return response

    def list(self):
        response = requests.get(self.cluster_url).json()
        _verify_response(response)
        return response

    def get(self, name: str):
        response = requests.get(f'{self.cluster_url}/{name}').json()
        _verify_response(response)
        return response

    def delete(self, name: str):
        response = requests.delete(f'{self.cluster_url}/{name}').json()
        _verify_response(response)
        return response

    def watch(self):
        for data in utils.watch_events(f'{self.cluster_url}?watch=true'):
            yield data