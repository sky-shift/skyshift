"""Informers manage the most-recent state of objects in a cache.

Informers are used to manage the most-recent state of objects in a cache. They are used to minimize pressure on the API server by reducing the number of API calls via watches.

Typical usage example:

    cluster_api = ClusterAPI()
    cluster_informer = Informer(cluster_api)
    cluster_informer.start()
    print(cluster_informer.get_cache())
"""
import queue
import threading
import time

from sky_manager.utils import generate_object
from sky_manager.api_client import ObjectAPI
from sky_manager.structs import Watcher
from sky_manager.templates.event_template import WatchEventEnum

class Informer(object):

    def __init__(self, api: ObjectAPI):
        self.api = api
        self.watcher = Watcher(self.api)
        self.informer_queue = queue.Queue()
        self.lock = threading.Lock()
        self.cache = {}

        # This thread reflects changes over the watch and populates the informer queue.
        self.reflector = threading.Thread(target=self._reflect_events)
        # The event controller thread consumes the informer queue and calls the add/delete/update callbacks.
        self.event_controller = threading.Thread(target=self._event_controller)

        # By default, callbacks do nothing.
        event_types = ['add', 'update', 'delete']
        self.callback_handler = {e_type: lambda x: x for e_type in event_types}

    def sync_cache(self):
        # Lists all available objects and populates the cache with such objects.
        api_response = self.api.list()
        api_object = generate_object(api_response)
        self.cache = {}
        for obj in api_object.objects:
            name = obj.meta.name
            self.cache[name] = obj

    def start(self):
        # Start the reflector and event controller threads.
        self.reflector.start()
        self.event_controller.start()

        # Populate informer cache.
        self.sync_cache()

    def join(self):
        # Join the reflector and event controller threads.
        self.reflector.join()
        self.event_controller.join()

    def add_event_callbacks(self, add_event_callback = None, update_event_callback = None, delete_event_callback = None):
        # Set the add, update, and delete callbacks.
        if add_event_callback:
            self.callback_handler['add'] = add_event_callback
        if update_event_callback:
            self.callback_handler['update'] = update_event_callback
        if delete_event_callback:
            self.callback_handler['delete'] = delete_event_callback

    def _reflect_events(self):
        for watch_event in self.watcher.watch():
            self.informer_queue.put(watch_event)

    def _event_controller(self):
        while True:
            watch_event = self.informer_queue.get()
            event_type = watch_event.event_type
            watch_obj = watch_event.object
            obj_name = watch_obj.meta.name

            if event_type == WatchEventEnum.ADD:
                with self.lock:
                    self.cache[obj_name] = watch_obj
                self.callback_handler['add'](watch_event)
            elif event_type == WatchEventEnum.UPDATE:
                with self.lock:
                    self.cache[obj_name] = watch_obj
                self.callback_handler['update'](watch_event)
            elif event_type == WatchEventEnum.DELETE:
                del self.cache[obj_name]
                self.callback_handler['delete'](watch_event)

    def get_cache(self):
        # Returns a cache at a given point in time.
        with self.lock:
            return self.cache


if __name__ == '__main__':
    from sky_manager.api_client import ClusterAPI
    cluster_api = ClusterAPI()
    informer = Informer(cluster_api)
    informer.start()
    while True:
        print(informer.get_cache())
        time.sleep(1)
