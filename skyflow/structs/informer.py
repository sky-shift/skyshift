"""Informers manage the most-recent state of objects in a cache.

Informers are used to manage the most-recent state of objects in
a cache. They are used to minimize pressure on the API server by
reducing the number of API calls via watches.

Typical usage example:

    cluster_api = ClusterAPI()
    cluster_informer = Informer(cluster_api)
    cluster_informer.start()
    print(cluster_informer.get_cache())
"""

import logging
import queue
import threading
import time
from typing import Any, Dict

from skyflow.structs import Watcher
from skyflow.templates.event_template import WatchEventEnum

logging.basicConfig(
    level=logging.INFO,
    format="%(name)s - %(asctime)s - %(levelname)s - %(message)s")


class Informer:  # pylint: disable=too-many-instance-attributes
    """Informer manages the most-recent state of objects in a cache.
    It regularly watches the API server and updates the cache asynchronously.
    """

    def __init__(self, api: object, logger=logging.getLogger("[Informer]")):
        self.api = api
        self.logger = logger
        self.watcher = Watcher(self.api)
        self.informer_queue: queue.Queue = queue.Queue()
        self.lock = threading.Lock()
        self.cache: Dict[str, Any] = {}

        # This thread reflects changes over the watch and
        # populates the informer queue.
        self.reflector = threading.Thread(target=self._reflect_events)
        # The event controller thread consumes the informer
        # queue and calls the add/delete/update callbacks.
        self.event_controller = threading.Thread(target=self._event_controller)

        # By default, callbacks do nothing.
        self.callback_handler: Dict[str, Any] = {}

    def sync_cache(self):
        """Lists all available objects and populates the cache with such objects."""
        api_object = self.api.list()
        self.cache = {}
        for obj in api_object.objects:
            name = obj.metadata.name
            self.cache[name] = obj

    def start(self):
        """Starts the informer."""
        # Start the reflector and event controller threads.
        self.reflector.start()
        self.event_controller.start()

        # Populate informer cache.
        self.sync_cache()

    def join(self):
        """Joins the informer threads."""
        # Join the reflector and event controller threads.
        self.reflector.join()
        self.event_controller.join()

    def add_event_callbacks(
        self,
        add_event_callback=None,
        update_event_callback=None,
        delete_event_callback=None,
    ):
        """Adds callbacks to the informer to populate controller event queue."""
        # Set the add, update, and delete callbacks.
        if add_event_callback:
            self.callback_handler["add"] = add_event_callback
        if update_event_callback:
            self.callback_handler["update"] = update_event_callback
        if delete_event_callback:
            self.callback_handler["delete"] = delete_event_callback

    def _reflect_events(self):
        for watch_event in self.watcher.watch():
            self.informer_queue.put(watch_event)

    def _event_controller(self):
        while True:
            watch_event = self.informer_queue.get()
            event_type = watch_event.event_type
            watch_obj = watch_event.object
            obj_name = watch_obj.get_name()

            if event_type == WatchEventEnum.ADD:
                with self.lock:
                    self.cache[obj_name] = watch_obj
                if "add" in self.callback_handler:
                    self.callback_handler["add"](watch_event)
            elif event_type == WatchEventEnum.UPDATE:
                old_obj = self.cache[obj_name]
                with self.lock:
                    self.cache[obj_name] = watch_obj
                if "update" in self.callback_handler:
                    self.callback_handler["update"](old_obj, watch_event)
            elif event_type == WatchEventEnum.DELETE:
                del self.cache[obj_name]
                if "delete" in self.callback_handler:
                    self.callback_handler["delete"](watch_event)

    def get_cache(self):
        """Returns the informer cache. at a given point in time."""
        with self.lock:
            self.logger.debug("Cache: %s", self.cache)
            return self.cache


if __name__ == "__main__":
    from skyflow.api_client import ClusterAPI

    cluster_api = ClusterAPI()
    informer = Informer(cluster_api)
    informer.start()
    while True:
        print(informer.get_cache())
        time.sleep(1)
