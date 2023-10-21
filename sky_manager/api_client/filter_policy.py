import requests
from string import Template

from sky_manager.api_server.api_server import DEFAULT_NAMESPACE, load_manager_config
from sky_manager import utils


def _verify_response(response):
    if 'error' in response:
        raise Exception(response['error'])


class FilterPolicyAPI(object):

    def __init__(self):
        self.host, self.port = load_manager_config()
        self.filter_url = Template(
            f'http://{self.host}:{self.port}/$namespace/filterpolicies')

    def Create(self, config: dict, namespace: str = DEFAULT_NAMESPACE):
        response = requests.post(
            self.filter_url.substitute(namespace=namespace),
            json=config).json()
        _verify_response(response)
        return response

    def Update(self, config: dict, namespace: str = DEFAULT_NAMESPACE):
        response = requests.put(
            self.filter_url.substitute(namespace=namespace),
            json=config).json()
        _verify_response(response)
        return response

    def List(self, namespace: str = DEFAULT_NAMESPACE):
        if namespace is None:
            filter_url = f'http://{self.host}:{self.port}/filterpolicies'
        else:
            filter_url = self.filter_url.substitute(namespace=namespace)
        response = requests.get(filter_url).json()
        _verify_response(response)
        return response

    def Get(self, policy: str, namespace: str = DEFAULT_NAMESPACE):
        filter_url = f'{self.filter_url.substitute(namespace=namespace)}/{policy}'
        response = requests.get(filter_url).json()
        _verify_response(response)
        return response

    def Delete(self, policy: str, namespace: str = DEFAULT_NAMESPACE):
        filter_url = f'{self.filter_url.substitute(namespace=namespace)}/{policy}'
        response = requests.delete(filter_url).json()
        _verify_response(response)
        return response

    def Watch(self, namespace: str = DEFAULT_NAMESPACE):
        if namespace is None:
            filter_url = f'http://{self.host}:{self.port}/filterpolicies'
        else:
            filter_url = self.filter_url.substitute(namespace=namespace)
        filter_url = f'{filter_url}?watch=true'
        for data in utils.watch_events(filter_url):
            yield data