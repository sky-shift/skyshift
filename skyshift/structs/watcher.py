# pylint: disable=cyclic-import
"""A watcher watches for changes to sets of objects.

Typical usage example:
    cluster_api = ClusterAPI()
    cluster_watcher = Watcher(cluster_api)
    # Blocks until an event is received.
    for event in cluster_watcher.watch():
        print(event)
"""
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(name)s - %(asctime)s - %(levelname)s - %(message)s")


class Watcher:  # pylint: disable=too-few-public-methods
    """Watches for changes to sets of objects."""

    def __init__(
        self,
        api: object,
    ):
        self.api = api

    def watch(self):
        """Watches for changes to objects."""
        try:
            for watch_event in self.api.watch():
                yield watch_event
        except Exception as error:  # pylint: disable=broad-except
            raise error


if __name__ == "__main__":
    # For debugging purposes...
    from skyshift.api_client import ClusterAPI

    cluster_api = ClusterAPI()
    watcher = Watcher(cluster_api)
    for lol in watcher.watch():
        print(lol)
        print(type(lol))
        print(lol.event_type)
