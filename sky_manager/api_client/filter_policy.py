import requests
from string import Template

from sky_manager.api_client import ObjectAPI, verify_response
from sky_manager.utils import utils

DEFAULT_NAMESPACE = 'default'

class FilterPolicyAPI(ObjectAPI):

    def __init__(self, namespace: str = DEFAULT_NAMESPACE):
        super().__init__()
        self.namespace = namespace
        self.filter_url = Template(
            f'http://{self.host}:{self.port}/$namespace/filterpolicies')

    def create(self, config: dict):
        assert self.namespace is not None, 'Create requires namespace.'
        filter_url = self.filter_url.substitute(namespace=self.namespace)
        response = requests.post(
            filter_url,
            json=config).json()
        return verify_response(response)

    def update(self, config: dict):
        assert self.namespace is not None, 'Update requires namespace.'
        filter_url = self.filter_url.substitute(namespace=self.namespace)
        response = requests.put(
            filter_url,
            json=config).json()
        return verify_response(response)

    def list(self):
        if self.namespace is None:
            filter_url = f'http://{self.host}:{self.port}/filterpolicies'
        else:
            filter_url = self.filter_url.substitute(namespace=self.namespace)
        response = requests.get(filter_url).json()
        return verify_response(response)

    def get(self, name: str):
        assert self.namespace is not None, 'Get requires namespace.'        
        filter_url = f'{self.filter_url.substitute(namespace=self.namespace)}/{name}'
        response = requests.get(filter_url).json()
        return verify_response(response)

    def delete(self, name: str):
        assert self.namespace is not None, 'Delete requires namespace.'
        filter_url = f'{self.filter_url.substitute(namespace=self.namespace)}/{name}'
        response = requests.delete(filter_url).json()
        return verify_response(response)

    def watch(self):
        if self.namespace is None:
            filter_url = f'http://{self.host}:{self.port}/filterpolicies'
        else:
            filter_url = self.filter_url.substitute(namespace=self.namespace)
        filter_url = f'{filter_url}?watch=true'
        for data in utils.watch_events(filter_url):
            yield verify_response(data)