# This controller manages the dynamic links between clusters. This assumes that each cluster has the
# Cluster link/Skupper software/deployment installed.
from contextlib import contextmanager
import logging
import queue
import requests
import traceback
from typing import Dict

from skyflow.controllers import Controller
from skyflow.structs import Informer
from skyflow.api_client import *
from skyflow.templates import Link, LinkStatusEnum, WatchEventEnum
from skyflow.network.cluster_linkv2 import create_link, delete_link
from skyflow.utils.utils import setup_cluster_manager

logging.basicConfig(
    level=logging.INFO,
    format='%(name)s - %(asctime)s - %(levelname)s - %(message)s')

@contextmanager
def LinkErrorHandler(controller: Controller):
    """Handles different types of errors from the Skylet Controller."""
    try:
        # Yield control back to the calling block
        yield
    except requests.exceptions.ConnectionError as e:
        controller.logger.error(traceback.format_exc())
        controller.logger.error(
            'Cannot connect to API server. Retrying.')
    except Exception as e:
        controller.logger.error(traceback.format_exc())

class LinkController(Controller):

    def __init__(self) -> None:
        super().__init__()
        self.logger = logging.getLogger('[Link Controller]')
        self.logger.setLevel(logging.INFO)

        #Thread safe queue for Informers to append events to.
        self.event_queue = queue.Queue()
        self.post_init_hook()

    def post_init_hook(self):
        def add_callback_fn(event):
            self.event_queue.put(event)
        
        def delete_callback_fn(event):
            self.event_queue.put(event)

        self.link_informer = Informer(LinkAPI())
        self.link_informer.add_event_callbacks(
            add_event_callback=add_callback_fn, delete_event_callback=delete_callback_fn)
        self.link_informer.start()

        self.cluster_informer = Informer(ClusterAPI())
        self.cluster_informer.start()

    def run(self):
        self.logger.info(
            'Running Link controller - Creates and deletes links across clusters.'
        )
        while True:
            with LinkErrorHandler(self):
                self.controller_loop()
    

    def controller_loop(self):
        # Blocks until there is at least 1 element in the queue or until timeout.
        event = self.event_queue.get()
        event_type = event.event_type 
        event_object = event.object
        if isinstance(event_object, Link):
            source = event_object.spec.source_cluster
            target = event_object.spec.target_cluster
            name = event_object.get_name()
            skip_update = False
            try: 
                if event_type == WatchEventEnum.ADD:
                    self.logger.info(f'Creating link between clusters. {source}, {target}')
                    self._create_link(source, target)
                    link_status = LinkStatusEnum.ACTIVE.value
                elif event_type == WatchEventEnum.DELETE:
                    self.logger.info(f'Deleting link between clusters. {source}, {target}')
                    self._delete_link(source, target)
                    skip_update = True
            except Exception as e:
                link_status = LinkStatusEnum.FAILED.value
            
            # Update the link status.
            if not skip_update:                 
                event_object.status.update_status(link_status)
                LinkAPI().update(event_object.model_dump(mode='json'))


    def _create_link(self, source: str, target: str) -> bool:
        """Creates a link between two clusters. Returns True if successful, False otherwise."""
        clusters_cache = self.cluster_informer.get_cache()
        source_cluster_manager = setup_cluster_manager(clusters_cache[source])
        target_cluster_manager = setup_cluster_manager(clusters_cache[target])
        try:
            create_link(source_manager = source_cluster_manager, target_manager = target_cluster_manager)
        except Exception as e:
            self.logger.error(traceback.format_exc())
            self.logger.error('Failed to create link between clusters.')
            raise e
    
    def _delete_link(self, source: str, target: str) -> bool:
        """Deletes a link between two clusters. Returns True if successful, False otherwise."""
        clusters_cache = self.cluster_informer.get_cache()
        source_cluster_manager = setup_cluster_manager(clusters_cache[source])
        target_cluster_manager = setup_cluster_manager(clusters_cache[target])
        try:
            delete_link(source_manager=source_cluster_manager, target_manager = target_cluster_manager)
        except Exception as e:
            self.logger.error(traceback.format_exc())
            self.logger.error('Failed to delete link between clusters.')
            raise e

if __name__ == '__main__':
    hc = LinkController()
    hc.run()
