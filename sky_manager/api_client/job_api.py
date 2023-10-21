import requests
from string import Template

from sky_manager.api_server.api_server import DEFAULT_NAMESPACE, load_manager_config
from sky_manager import utils


def _verify_response(response):
    if 'error' in response:
        raise Exception(response['error'])


class JobAPI(object):

    def __init__(self):
        self.host, self.port = load_manager_config()
        self.job_url = Template(
            f'http://{self.host}:{self.port}/$namespace/jobs')

    def Create(self, config: dict, namespace: str = DEFAULT_NAMESPACE):
        response = requests.post(self.job_url.substitute(namespace=namespace),
                                 json=config).json()
        _verify_response(response)
        return response

    def Update(self, config: dict, namespace: str = DEFAULT_NAMESPACE):
        response = requests.put(self.job_url.substitute(namespace=namespace),
                                json=config).json()
        _verify_response(response)
        return response

    def List(self, namespace: str = DEFAULT_NAMESPACE):
        if namespace is None:
            job_url = f'http://{self.host}:{self.port}/jobs'
        else:
            job_url = self.job_url.substitute(namespace=namespace)
        response = requests.get(job_url).json()
        _verify_response(response)
        return response

    def Get(self, job: str, namespace: str = DEFAULT_NAMESPACE):
        job_url = f'{self.job_url.substitute(namespace=namespace)}/{job}'
        response = requests.get(job_url).json()
        _verify_response(response)
        return response

    def Delete(self, job: str, namespace: str = DEFAULT_NAMESPACE):
        job_url = f'{self.job_url.substitute(namespace=namespace)}/{job}'
        response = requests.delete(job_url).json()
        _verify_response(response)
        return response

    def Watch(self, namespace: str = DEFAULT_NAMESPACE):
        if namespace is None:
            job_url = f'http://{self.host}:{self.port}/jobs'
        else:
            job_url = self.job_url.substitute(namespace=namespace)
        job_url = f'{job_url}?watch=true'
        for data in utils.watch_events(job_url):
            yield data


def ListJobs():
    host, port = load_api_service()
    watch_url = f'http://{host}:{port}/jobs'
    response = requests.get(watch_url).json()
    # Ugly Code
    if 'error' in response:
        raise Exception(response['error'])
    return response


def GetJob(job: str):
    host, port = load_api_service()
    watch_url = f'http://{host}:{port}/jobs/{job}'
    response = requests.get(watch_url).json()
    if 'error' in response:
        raise Exception(response['error'])
    return response


def WatchJobs():
    host, port = load_api_service()
    watch_url = f'http://{host}:{port}/watch/jobs'
    for data in utils.watch_events(watch_url):
        yield data


def CreateJob(config: dict):
    host, port = load_api_service()
    watch_url = f'http://{host}:{port}/jobs'
    response = requests.post(watch_url, json=config)
    return response.json()


def DeleteJob(job: str):
    host, port = load_api_service()
    delete_url = f'http://{host}:{port}/jobs/{job}'
    response = requests.delete(delete_url)
    return response.json()
