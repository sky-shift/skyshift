import requests

from sky_manager import utils


# Hardcoded for now.
def load_api_service():
    return 'localhost', 50051


def ListClusters():
    host, port = load_api_service()
    watch_url = f'http://{host}:{port}/clusters'
    response = requests.get(watch_url).json()
    if 'error' in response:
        raise Exception(response['error'])
    return response


def GetCluster(cluster: str):
    host, port = load_api_service()
    watch_url = f'http://{host}:{port}/clusters/{cluster}'
    response = requests.get(watch_url).json()
    if 'error' in response:
        raise Exception(response['error'])
    return response


def WatchClusters():
    host, port = load_api_service()
    watch_url = f'http://{host}:{port}/watch/clusters'
    for data in utils.watch_events(watch_url):
        yield data


def CreateCluster(config: dict):
    host, port = load_api_service()
    watch_url = f'http://{host}:{port}/clusters'
    response = requests.post(watch_url, json=config)
    return response.json()


def DeleteCluster(cluster: str):
    host, port = load_api_service()
    delete_url = f'http://{host}:{port}/clusters/{cluster}'
    response = requests.delete(delete_url)
    return response.json()
