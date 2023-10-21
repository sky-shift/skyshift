import json
import threading
import time

import requests

from sky_manager.cluster_manager.kubernetes_manager import KubernetesManager
from sky_manager.templates import Cluster


# Hardcoded for now.
def load_api_service():
    return 'localhost', 50051


def watch_events(url):
    response = requests.get(url, stream=True)
    for line in response.iter_lines():
        if line:
            data = json.loads(line.decode('utf-8'))
            yield data


class Informer(object):

    def __init__(self, key):
        host, port = load_api_service()
        self.list_url = f'http://{host}:{port}/{key}'
        self.watch_url = f'{self.list_url}?watch=true'
        self.lock = threading.Lock()
        self.cache = {}
        # Call List
        response = requests.get(self.list_url).json()
        for itm in response['items']:
            self.cache[itm['metadata']['name']] = itm

        self.add_event_callback = None
        self.delete_event_callback = None

    def start(self):
        self.watch_process = threading.Thread(target=self.watch)
        self.watch_process.start()

    def join(self):
        self.watch_process.join()

    def add_event_callbacks(self, add_event_callback, delete_event_callback):
        self.add_event_callback = add_event_callback
        self.delete_event_callback = delete_event_callback

    def watch(self):
        while True:
            try:
                for data in watch_events(self.watch_url):
                    assert data[
                        'kind'] == 'WatchEvent', "Not a WatchEvent object"
                    if data['type'] == 'Added':
                        for k, v in data['object'].items():
                            k = k.split('/')[-1]
                            with self.lock:
                                self.cache[k] = v
                                if self.add_event_callback:
                                    self.add_event_callback((k, v))
                    elif data['type'] == 'Deleted':
                        for k, v in data['object'].items():
                            with self.lock:
                                k = k.split('/')[-1]
                                del self.cache[k]
                                if self.delete_event_callback:
                                    self.delete_event_callback((k, v))
                    else:
                        print("Ignoring Unknown event")
            except requests.exceptions.ChunkedEncodingError:
                print("Connection closed. Reconnecting...")
                time.sleep(1)
                continue
            except requests.exceptions.ConnectionError:
                print("API Server closed. Aborting watch.")
                break

    def get_cache(self):
        with self.lock:
            return self.cache


def setup_cluster_manager(cluster_obj: Cluster):
    cluster_type = cluster_obj.spec.manager
    cluster_name = cluster_obj.meta.name

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
    args = {
        k: v
        for k, v in dict(cluster_obj.meta).items() if k in class_params
    }
    # Create an instance of the class with the extracted arguments.
    return cluster_manager_cls(**args)


if __name__ == '__main__':
    informer = Informer('clusters')
    informer.start()
    while True:
        print(informer.get_cache())
        time.sleep(1)