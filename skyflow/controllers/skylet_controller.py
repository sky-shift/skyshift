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

from skyflow.api_client import ClusterAPI
from skyflow.cluster_lookup import lookup_kube_config
from skyflow.controllers.controller import Controller
from skyflow.skylet.skylet import launch_skylet
from skyflow.templates import Cluster, ClusterStatusEnum
from skyflow.templates.event_template import WatchEventEnum
from skyflow.structs import Informer

SKYLET_CONTROLLER_INTERVAL = 0.5

logging.basicConfig(
    level=logging.INFO,
    format='%(name)s - %(asctime)s - %(levelname)s - %(message)s')


def terminate_process(pid: int):
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
            'Cannot connect to API server. Retrying.')
    except Exception as e:
        controller.logger.error(traceback.format_exc())


class SkyletController(Controller):

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(f'[Skylet Controller]')
        self.logger.setLevel(logging.INFO)
        # Python thread safe queue for Informers to append events to.
        self.event_queue = Queue()
        self.skylets = {}

    def post_init_hook(self):
        """Declares a Cluster informer that watches all changes to all cluster objects."""
        cluster_api = ClusterAPI()
        self.cluster_informer = Informer(cluster_api)

        def add_callback_fn(event):
            self.event_queue.put(event)
        
        def update_callback_fn(event):
            event_object = event.object
            if event_object.get_status() == ClusterStatusEnum.ERROR:
                self.event_queue.put(event)

        def delete_callback_fn(event):
            self.event_queue.put(event)

        # Add to event queue if cluster is added (or modified) or deleted.
        self.cluster_informer.add_event_callbacks(
            add_event_callback=add_callback_fn,
            update_event_callback=update_callback_fn,
            delete_event_callback=delete_callback_fn)
        self.cluster_informer.start()



    def run(self):
        # Establish a watch over added clusters.
        self.logger.info(
            'Executing Skylet controller - Manages launching and terminating Skylets for clusters.'
        )
        self._load_clusters()
        while True:
            with SkyletControllerErrorHandler(self):
                self.controller_loop()
            # Serves as a form of rate limiting.
            # TODO(mluo): Move rate limiting to the event queue.
            time.sleep(SKYLET_CONTROLLER_INTERVAL)
    
    def controller_loop(self):
        watch_event = self.event_queue.get()
        event_type = watch_event.event_type
        cluster_obj = watch_event.object
        cluster_name = cluster_obj.get_name()
        # Launch Skylet if it is a newly added cluster.
        if event_type == WatchEventEnum.ADD:
            self._launch_skylet(cluster_obj)
            self.logger.info(
                    f'Launched Skylet for cluster: {cluster_name}.')
        elif event_type in [WatchEventEnum.DELETE, WatchEventEnum.UPDATE]:
            # Terminate Skylet controllers if the cluster is deleted.
            self._terminate_skylet(cluster_obj)
            self.logger.info(
                f'Terminated Skylet for cluster: {cluster_name}.')
    
    def _load_clusters(self):
        existing_clusters = lookup_kube_config()
        for cluster_name in existing_clusters:
            try:
                cluster_obj = ClusterAPI().get(cluster_name)
            except Exception as e:
                cluster_dictionary = {
                    'kind': 'Cluster',
                    'metadata': {
                        'name': cluster_name,
                    },
                    'spec': {
                        'manager': 'k8',
                    }
                }
                cluster_obj = ClusterAPI().create(config=cluster_dictionary)
            self._launch_skylet(cluster_obj)


    
    def _launch_skylet(self, cluster_obj: Cluster):
        """Hidden method that launches Skylet in a Python thread."""
        cluster_name = cluster_obj.get_name()
        if cluster_name in self.skylets:
            return
        # Launch a Skylet to manage the cluster state.
        skylet_process = multiprocessing.Process(target=launch_skylet,
                                                 args=(cluster_name, ))
        skylet_process.start()
        self.skylets[cluster_name] = skylet_process

    def _terminate_skylet(self, cluster_obj: Cluster):
        """Hidden method that terminates Skylet."""
        cluster_name = cluster_obj.get_name()
        if cluster_name not in self.skylets:
            return
        terminate_process(self.skylets[cluster_name].pid)
        del self.skylets[cluster_name]



# Testing purposes.
if __name__ == '__main__':
    cont = SkyletController()
    cont.run()