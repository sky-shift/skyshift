import requests
from tabulate import tabulate

from sky_manager import utils


# Hardcoded for now.
def load_api_service():
    return 'localhost', 50051


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
