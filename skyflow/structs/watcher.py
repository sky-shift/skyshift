"""A watcher watches for changes to sets of objects.

Typical usage example:

    cluster_api = ClusterAPI()
    cluster_watcher = Watcher(cluster_api)
    # Blocks until an event is received.
    for event in cluster_watcher.watch():
        print(event)
"""
import logging
import requests
import time
import traceback

from skyflow.templates.event_template import WatchEvent

# TODO(mluo): Make backoff exponential.
BACKOFF_TIME = 3
DEFAULT_RETRY_LIMIT = 1e9

logger = logging.getLogger(__name__)

class Watcher:
    def __init__(self, api: object, retry_limit: int = DEFAULT_RETRY_LIMIT, backoff_time: int = BACKOFF_TIME):
        self.api = api
        self.retry_limit = retry_limit
        self.backoff_time = backoff_time
    
    def watch(self):
        retry = 0
        while True:
            try:
                for watch_event in self.api.watch():
                    yield watch_event
            except requests.exceptions.ChunkedEncodingError:
                retry += 1
                logger.error('API server restarting. Reconnecting...')
                time.sleep(self.backoff_time)
            except requests.exceptions.ConnectionError:
                retry += 1
                logger.error('Unable to connect to API Server closed. Trying again.')
                time.sleep(self.backoff_time)
            except Exception as e:
                retry+=1
                logger.error(traceback.format_exc())
                logger.error('Encountered unusual error. Trying again.')
                time.sleep(self.backoff_time)
            if retry >= self.retry_limit:
                logger.error('Retry limit exceeded. Terminating watch.')
                break


if __name__ == '__main__':
    from skyflow.api_client import ClusterAPI
    cluster_api = ClusterAPI()
    watcher = Watcher(cluster_api)
    for lol in watcher.watch():
        print(lol)
        print(type(lol))
        print(lol.event_type)
