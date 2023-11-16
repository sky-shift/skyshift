import requests

from sky_manager.api_client import ObjectAPI, verify_response
from sky_manager.utils import watch_events

class ClusterAPI(ObjectAPI):

    def __init__(self):
        super().__init__()
        self.cluster_url = f'http://{self.host}:{self.port}/clusters'

    def create(self, config: dict):
        response = requests.post(self.cluster_url, json=config).json()
        obj = verify_response(response)
        return obj

    def update(self, config: dict):
        response = requests.put(self.cluster_url, json=config).json()
        obj = verify_response(response)
        return obj

    def list(self):
        response = requests.get(self.cluster_url).json()
        obj = verify_response(response)
        return obj

    def get(self, name: str):
        response = requests.get(f'{self.cluster_url}/{name}').json()
        obj = verify_response(response)
        return obj

    def delete(self, name: str):
        response = requests.delete(f'{self.cluster_url}/{name}').json()
        obj = verify_response(response)
        return obj

    def watch(self):
        for data in watch_events(f'{self.cluster_url}?watch=true'):
            yield verify_response(data)