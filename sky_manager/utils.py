import json
import queue
import threading
import time

import requests

from sky_manager.api_server.api_server import load_manager_config
from sky_manager.cluster_manager.kubernetes_manager import KubernetesManager
from sky_manager.templates import Cluster
from sky_manager.templates.event_template import WatchEventEnum

def watch_events(url):
    response = requests.get(url, stream=True)
    for line in response.iter_lines():
        if line:
            data = json.loads(line.decode('utf-8'))
            yield data


class Informer(object):

    def __init__(self, key: str):
        host, port = load_manager_config()
        self.list_url = f'http://{host}:{port}/{key}'
        self.watch_url = f'{self.list_url}?watch=true'
        self.informer_queue = queue.Queue()
        self.lock = threading.Lock()
        self.cache = {}

        # Populate informer cache.
        self._sync_cache()

        self.add_event_callback = lambda x: x
        self.delete_event_callback = lambda x: x
        self.update_event_callback = lambda x: x

    def _sync_cache(self):
        response = requests.get(self.list_url).json()
        for itm in response['items']:
            item_name = itm['metadata']['name']
            self.cache[item_name] = itm

    def start(self):
        self.reflector = threading.Thread(target=self._reflect_events)
        self.event_controller = threading.Thread(target=self._event_controller)
        self.reflector.start()
        self.event_controller.start()

    def join(self):
        self.reflector.join()
        self.event_controller.join()

    def add_event_callbacks(self, add_event_callback = None, update_event_callback = None, delete_event_callback = None):
        self.add_event_callback = add_event_callback
        self.update_event_callback = update_event_callback
        self.delete_event_callback = delete_event_callback

    def _reflect_events(self):
        while True:
            try:
                for data in watch_events(self.watch_url):
                    assert data['kind'] == 'WatchEvent', "Not a WatchEvent object"
                    watch_object = list(data['object'].items())[0][1]
                    if data['type'] == WatchEventEnum.ADD:
                        self.informer_queue.put((WatchEventEnum.ADD, watch_object))
                    elif data['type'] == WatchEventEnum.UPDATE:
                        self.informer_queue.put((WatchEventEnum.UPDATE, watch_object))
                    elif data['type'] == WatchEventEnum.DELETE:
                        self.informer_queue.put((WatchEventEnum.DELETE, watch_object))
            except requests.exceptions.ChunkedEncodingError:
                print("API server restarting. Reconnecting...")
                time.sleep(1)
                continue
            except requests.exceptions.ConnectionError:
                print("Unable to connect to API Server closed. Trying again.")
                time.sleep(5)
                continue
            finally:
                pass

    def _event_controller(self):
        while True:
            event_type, event_object = self.informer_queue.get()
            object_name = event_object['metadata']['name']
            if event_type == WatchEventEnum.ADD:
                with self.lock:
                    self.cache[object_name] = event_object
                self.add_event_callback(event_object)
            elif event_type == WatchEventEnum.UPDATE:
                with self.lock:
                    self.cache[object_name] = event_object
                self.update_event_callback(event_object)
            elif event_type == WatchEventEnum.DELETE:
                del self.cache[object_name]
                self.delete_event_callback(event_object)

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