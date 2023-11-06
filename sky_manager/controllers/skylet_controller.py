"""Skylet Controller.

Manages launching and terminating Skylets for clusters. Each cluster corresponds to a Skylet.
If a new cluster is detected (e.g. in INIT state), a Skylet is launched to track and coordinate
the cluster's state. If a cluster is deleted, the corresponding Skylet is terminated.
"""

from contextlib import contextmanager
import multiprocessing
import logging
import psutil
from queue import Queue
import requests
import time
import traceback

from sky_manager.api_client import *
from sky_manager.controllers.controller import Controller
from sky_manager.skylet.skylet import launch_skylet
from sky_manager.templates.cluster_template import Cluster, ClusterStatusEnum
from sky_manager.utils import Informer

SKYLET_CONTROLLER_INTERVAL = 0.5


def terminate_process(pid):
    """Terminates a process and all its children."""
    parent = psutil.Process(pid)
    for child in parent.children(recursive=True):
        child.terminate()
    parent.terminate()


@contextmanager
def SkyletControllerErrorHandler(controller: Controller):
    """Handles different types of errors from the Skylet Controller."""
    try:
        # Yield control back to the calling block
        yield
    except requests.exceptions.ConnectionError as e:
        controller.logger.error(traceback.format_exc())
        controller.logger.error(
            'Cannot connect to API server, trying again...')
    except Exception as e:
        controller.logger.error(traceback.format_exc())


class SkyletController(Controller):

    def __init__(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(f'Skylet Controller')
        self.logger.setLevel(logging.INFO)
        # Python thread safe queue for Informers to append events to.
        self.event_queue = Queue()
        self.skylets = {}
        # Calls into post_init_hook.
        super().__init__()

    def post_init_hook(self):
        """Declares a Cluster informer that watches all changes to all cluster objects."""
        self.cluster_informer = Informer('clusters')

        def add_callback_fn(event):
            self.event_queue.put(event)

        def delete_callback_fn(event):
            self.event_queue.put(event)

        # Add to event queue if cluster is added (or modified) or deleted.
        self.cluster_informer.add_event_callbacks(
            add_event_callback=add_callback_fn,
            delete_event_callback=delete_callback_fn)
        self.cluster_informer.start()

    def run(self):
        # Establish a watch over added clusters.
        self.logger.info(
            'Executing Skylet controller - Manages launching and terminating Skylets for clusters.'
        )
        while True:
            with SkyletControllerErrorHandler(self):
                self.controller_loop()
            # Serves as a form of rate limiting.
            # TODO(mluo): Move rate limiting to the event queue.
            time.sleep(SKYLET_CONTROLLER_INTERVAL)
    
    def controller_loop(self):
        event = self.event_queue.get()
        cluster_name = event[0]
        cluster_obj = event[1]
        # TODO(mluo): Fix bug, ETCD Delete Watch Event does not return deleted value.
        if not event[1]:
            # If Cluster has been deleted, terminate Skylet corresponding to the cluster.
            self._terminate_skylet(cluster_name)
            self.logger.info(
                f'Terminated Skylet for cluster: {cluster_name}.')
        else:
            cluster_obj = Cluster.from_dict(event[1])
            if cluster_obj.get_status() == ClusterStatusEnum.INIT:
                self._launch_skylet(cluster_obj)
                self.logger.info(
                    f'Launched Skylet for cluster: {cluster_name}.')
    
    def _launch_skylet(self, cluster_obj):
        """Hidden method that launches Skylet in a Python thread."""
        cluster_name = cluster_obj.meta.name
        if cluster_name in self.skylets:
            return
        # Launch a Skylet to manage the cluster state.
        skylet_process = multiprocessing.Process(target=launch_skylet,
                                                 args=(dict(cluster_obj), ))
        skylet_process.start()
        self.skylets[cluster_name] = skylet_process

    def _terminate_skylet(self, cluster_name):
        """Hidden method that terminates Skylet."""
        if cluster_name not in self.skylets:
            return
        terminate_process(self.skylets[cluster_name].pid)
        del self.skylets[cluster_name]



# Testing purposes.
if __name__ == '__main__':
    a = SkyletController()
    a.run()