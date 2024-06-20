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
import threading
import time
import traceback
from queue import Empty, Queue
from typing import Any, Dict

import requests

from skyshift.structs.watcher import Watcher
from skyshift.templates.event_template import WatchEvent, WatchEventEnum

DEFAULT_RETRY_LIMIT = int(1e9)
MAX_BACKOFF_TIME = 16  # seconds
CACHE_RESYNC_PERIOD = 1800  # every 30 minutes

logging.basicConfig(
    level=logging.INFO,
    format="%(name)s - %(asctime)s - %(levelname)s - %(message)s")


class Informer:  # pylint: disable=too-many-instance-attributes
    """Informer manages the most-recent state of objects in a cache.
    It regularly watches the API server and updates the cache asynchronously.
    """

    def __init__(  # pylint: disable=too-many-arguments
            self,
            api: object,
            logger=logging.getLogger("[Informer]"),
            cache_resync_period=CACHE_RESYNC_PERIOD,
            retry_limit: int = DEFAULT_RETRY_LIMIT,
            max_backoff_time: int = MAX_BACKOFF_TIME):
        self.api = api
        self.logger = logger
        self.watcher = Watcher(self.api)
        self.informer_queue: Queue = Queue()
        self.lock = threading.Lock()
        self.cache: Dict[str, Any] = {}
        self.cache_resync_period = cache_resync_period
        self.retry_limit = retry_limit
        self.max_backoff_time = max_backoff_time

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

    def resync_cache(self):
        """Resync the cache with the API server."""
        api_object = self.api.list()
        obj_names = {obj.get_name() for obj in api_object.objects}
        for obj in api_object.objects:
            watch_event_type = None
            obj_name = obj.get_name()

            if obj_name in self.cache:
                if obj != self.cache[obj_name]:
                    watch_event_type = WatchEventEnum.UPDATE
            else:
                watch_event_type = WatchEventEnum.ADD

            if watch_event_type:
                watch_event = WatchEvent(event_type=watch_event_type,
                                         object=obj)
                self.informer_queue.put(watch_event)

        # For objects not in the cache, add a 'DELETED' event
        # to the informer queue.
        cache_keys = [
            obj_name for obj_name in self.cache if obj_name not in obj_names
        ]
        for obj_name in cache_keys:
            watch_event = WatchEvent(event_type=WatchEventEnum.DELETE,
                                     object=self.cache[obj_name])
            self.informer_queue.put(watch_event)

    def start(self):
        """Starts the informer."""
        # Populate informer cache.
        self.sync_cache()
        # Start the reflector and event controller threads.
        self.reflector.start()
        self.event_controller.start()

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
        """Establishes a watch and appends modifications to a queue."""
        retry = 0
        backoff_time = 1
        while True:
            try:
                self.resync_cache()
                retry = 0
                backoff_time = 1
                for watch_event in self.watcher.watch():
                    self.informer_queue.put(watch_event)
            except Exception as error:  # pylint: disable=broad-except
                retry += 1
                if isinstance(error, requests.exceptions.ConnectionError):
                    self.logger.error("Unable to connect to API Server.")
                elif isinstance(error,
                                requests.exceptions.ChunkedEncodingError):
                    self.logger.error("API server restarting. Reconnecting...")
                else:
                    self.logger.error(traceback.format_exc())
                    self.logger.error(
                        "Encountered unusual error. Trying again.")
                time.sleep(backoff_time)
                backoff_time = min(backoff_time * 2, self.max_backoff_time)
                if retry >= self.retry_limit:
                    self.logger.error(
                        "Retry limit exceeded. Terminating informer.")
                    break

    def _event_controller(self):
        resync_start_time = time.time()
        while True:
            cur_time = time.time()
            wait_time = self.cache_resync_period - (cur_time -
                                                    resync_start_time)
            if wait_time < 0:
                wait_time = 1
            try:
                watch_event = self.informer_queue.get(timeout=wait_time)
            except Empty:
                resync_start_time = time.time()
                self.resync_cache()
                continue
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

    def set_retry_limit(self, retry_limit: int):
        """Sets the retry limit."""
        self.retry_limit = retry_limit


if __name__ == "__main__":
    from skyshift.api_client import ClusterAPI

    cluster_api = ClusterAPI()
    informer = Informer(cluster_api)
    informer.start()
    while True:
        print(informer.get_cache())
        time.sleep(10)
