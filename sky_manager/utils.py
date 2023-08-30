import json
import threading
import time

import requests
from multiprocessing import Manager, Lock, Process
import time
from threading import Lock

from sky_manager.cluster_manager.kubernetes_manager import KubernetesManager


class ThreadSafeDict:

    def __init__(self):
        self.lock = threading.Lock()
        self.dict = {}

    def set(self, key, value):
        with self.lock:
            self.dict[key] = value

    def get(self, key):
        with self.lock:
            return self.dict.get(key)

    def delete(self, key):
        with self.lock:
            if key in self.dict:
                del self.dict[key]

    def items(self):
        with self.lock:
            return list(self.dict.items())

    def __repr__(self):
        return str(self.dict)


# Hardcoded for now.
def load_api_service():
    return 'localhost', 50051


def watch_events(url):
    response = requests.post(url, stream=True)
    for line in response.iter_lines():
        if line:
            data = json.loads(line.decode('utf-8'))
            yield data


class Informer(object):

    def __init__(self, key):
        host, port = load_api_service()
        self.watch_url = f'http://{host}:{port}/watch/{key}'
        self.list_url = f'http://{host}:{port}/{key}'
        self.lock = Lock()
        self.object = Manager().dict()
        # Call List
        response = requests.get(self.list_url).json()
        response_type = response['kind']
        print(response_type)
        if response_type in ['Cluster'
                             'Job']:
            cluster_name = response['metadata']['name']
            self.object[cluster_name] = response
        elif response_type in ['ClusterList', 'JobList']:
            cluster_items = response['items']
            for cluster_response in cluster_items:
                cluster_name = cluster_response['metadata']['name']
                self.object[cluster_name] = cluster_response
        else:
            raise ValueError(f'Unknown object type: {response_type}')

    def start(self):
        self.watch_process = Process(target=self.watch)
        self.watch_process.start()
        #watch_process.join()

    def watch(self):
        while True:
            try:
                for data in watch_events(self.watch_url):
                    assert data[
                        'kind'] == 'WatchEvent', "Not a WatchEvent object"
                    if data['type'] == 'Added':
                        for k, v in data['object'].items():
                            with self.lock:
                                self.object[k] = json.loads(v)
                    elif data['type'] == 'Deleted':
                        for k, v in data['object'].items():
                            with self.lock:
                                del self.object[k]
                    else:
                        print("Ignoring Unknown event")
            except requests.exceptions.ChunkedEncodingError:
                print("Connection closed. Reconnecting...")
                time.sleep(1)
                continue
            except requests.exceptions.ConnectionError:
                print("API Server closed. Aborting watch.")
                break

    def get_object(self):
        return self.object


def setup_cluster_manager(cluster_config):
    metadata = cluster_config['metadata']
    cluster_type = metadata['manager_type']

    if cluster_type in ['k8', 'kubernetes']:
        cluster_manager_cls = KubernetesManager
    else:
        raise ValueError(f"Cluster type {cluster_type} not supported.")

    # Get the constructor of the class
    constructor = cluster_manager_cls.__init__
    # Get the parameter names of the constructor
    class_params = constructor.__code__.co_varnames[1:constructor.__code__.
                                                    co_argcount]

    # Filter the dictionary keys based on parameter names
    args = {k: v for k, v in metadata.items() if k in class_params}
    # Create an instance of the class with the extracted arguments.
    return cluster_manager_cls(**args)