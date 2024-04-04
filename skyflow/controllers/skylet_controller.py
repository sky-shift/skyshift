"""Skylet Controller.

Manages launching and terminating Skylets for clusters. Each cluster corresponds to a Skylet.
If a new cluster is detected (e.g. in INIT state), a Skylet is launched to track and coordinate
the cluster's state. If a cluster is deleted, the corresponding Skylet is terminated.
"""

import multiprocessing
import time
from queue import Queue

import psutil

from skyflow.api_client import ClusterAPI
from skyflow.api_client.object_api import APIException
from skyflow.cluster_lookup import lookup_kube_config
from skyflow.controllers import Controller, controller_error_handler
from skyflow.controllers.controller_utils import create_controller_logger
from skyflow.globals import SKYCONF_DIR
from skyflow.skylet.skylet import launch_skylet
from skyflow.structs import Informer
from skyflow.templates import Cluster, ClusterStatusEnum
from skyflow.templates.event_template import WatchEventEnum

SKYLET_CONTROLLER_INTERVAL = 0.5


def terminate_process(pid: int):
    """Terminates a process and all its children."""
    parent = psutil.Process(pid)
    for child in parent.children(recursive=True):
        child.terminate()
    parent.terminate()


class SkyletController(Controller):
    """Skylet Controller - Spawns Skylets for each cluster."""

    def __init__(self):
        super().__init__()
        self.logger = create_controller_logger(
            title="[Skylet Controller]",
            log_path=f'{SKYCONF_DIR}/skylet_controller.log')
        # Python thread safe queue for Informers to append events to.
        self.event_queue = Queue()
        self.skylets = {}
        self.cluster_api = ClusterAPI()
        self.cluster_informer = Informer(self.cluster_api, logger=self.logger)

    def post_init_hook(self):
        """Declares a Cluster informer that watches all changes to all cluster objects."""

        def update_callback_fn(_, event):
            event_object = event.object
            self.logger.debug("Cluster status: %s", event_object.get_status())
            if event_object.get_status() in [
                    ClusterStatusEnum.ERROR, ClusterStatusEnum.READY
            ]:
                self.event_queue.put(event)

        def delete_callback_fn(event):
            self.logger.debug("Cluster deleted: %s", event.object.get_name())
            self.event_queue.put(event)

        # Add to event queue if cluster is added (or modified) or deleted.
        self.cluster_informer.add_event_callbacks(
            update_event_callback=update_callback_fn,
            delete_event_callback=delete_callback_fn,
        )
        self.cluster_informer.start()

    def run(self):
        # Establish a watch over added clusters.
        self.logger.info(
            "Executing Skylet controller - Manages launching and terminating Skylets for clusters."
        )
        self._load_clusters()
        while True:
            with controller_error_handler(self):
                self.controller_loop()
            # Serves as a form of rate limiting.
            # @TODO(mluo): Move rate limiting to the event queue.
            time.sleep(SKYLET_CONTROLLER_INTERVAL)

    def controller_loop(self):
        watch_event = self.event_queue.get()
        event_type = watch_event.event_type
        cluster_obj = watch_event.object
        cluster_name = cluster_obj.get_name()
        # Launch Skylet for clusters that are finished provisioning.
        if event_type == WatchEventEnum.UPDATE and cluster_obj.get_status(
        ) == ClusterStatusEnum.READY:
            if cluster_name not in self.skylets:
                self._launch_skylet(cluster_obj)
                self.logger.info('Launched Skylet for cluster: %s.',
                                 cluster_name)
        else:
            # Terminate Skylet controllers if the cluster is deleted.
            self._terminate_skylet(cluster_obj)
            self.logger.info("Terminated Skylet for cluster: %s.",
                             cluster_name)

    def _load_clusters(self):
        existing_clusters = lookup_kube_config(self.cluster_api)
        self.logger.info("Found existing clusters: %s.", existing_clusters)
        for cluster_name in existing_clusters:
            self.logger.info("Found existing cluster: %s.", cluster_name)
            try:
                cluster_obj = ClusterAPI().get(cluster_name)
            except APIException:
                cluster_dictionary = {
                    "kind": "Cluster",
                    "metadata": {
                        "name": cluster_name,
                    },
                    "spec": {
                        "manager": "k8",
                    },
                }
                try:
                    cluster_obj = ClusterAPI().create(
                        config=cluster_dictionary)
                except APIException as error:
                    self.logger.error(
                        "Failed to create cluster: %s. Error: %s",
                        cluster_name, error)
                    continue
            self._launch_skylet(cluster_obj)

    def _launch_skylet(self, cluster_obj: Cluster):
        """Hidden method that launches Skylet in a Python thread."""
        cluster_name = cluster_obj.get_name()
        if cluster_name in self.skylets:
            return
        # Launch a Skylet to manage the cluster state.
        self.logger.info("Launching Skylet for cluster: %s.", cluster_name)
        skylet_process = multiprocessing.Process(target=launch_skylet,
                                                 args=(cluster_obj, ))
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
if __name__ == "__main__":
    cont = SkyletController()
    cont.run()
