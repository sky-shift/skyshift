import requests
from string import Template

from sky_manager.api_client import ObjectAPI, verify_response
from sky_manager.utils import utils

DEFAULT_NAMESPACE = 'default'

class JobAPI(ObjectAPI):

    def __init__(self, namespace: str = DEFAULT_NAMESPACE):
        super().__init__()
        self.namespace = namespace
        self.job_url = Template(
            f'http://{self.host}:{self.port}/$namespace/jobs')

    def create(self, config: dict):
        assert self.namespace is not None, 'Create requires namespace.'
        job_url = self.job_url.substitute(namespace=self.namespace)

        response = requests.post(job_url, json=config)
        response = response.json()
        return verify_response(response)

    def update(self, config: dict):
        assert self.namespace is not None, 'Update requires namespace.'
        job_url = self.job_url.substitute(namespace=self.namespace)
        response = requests.put(job_url,
                                json=config).json()
        return verify_response(response)

    def list(self):
        if self.namespace is None:
            job_url = f'http://{self.host}:{self.port}/jobs'
        else:
            job_url = self.job_url.substitute(namespace=self.namespace)
        response = requests.get(job_url).json()
        return verify_response(response)

    def get(self, name: str):
        assert self.namespace is not None, 'Get requires namespace.'
        job_url = f'{self.job_url.substitute(namespace=self.namespace)}/{name}'
        response = requests.get(job_url).json()
        return verify_response(response)

    def delete(self, name: str):
        assert self.namespace is not None, 'Delete requires namespace.'
        job_url = f'{self.job_url.substitute(namespace=self.namespace)}/{name}'
        response = requests.delete(job_url).json()
        return verify_response(response)

    def watch(self):
        if self.namespace is None:
            job_url = f'http://{self.host}:{self.port}/jobs'
        else:
            job_url = self.job_url.substitute(namespace=self.namespace)
        job_url = f'{job_url}?watch=true'
        for data in utils.watch_events(job_url):
            yield verify_response(data)