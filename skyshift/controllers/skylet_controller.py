"""Skylet Controller.

Manages launching and terminating Skylets for clusters. Each cluster corresponds to a Skylet.
If a new cluster is detected (e.g. in INIT state), a Skylet is launched to track and coordinate
the cluster's state. If a cluster is deleted, the corresponding Skylet is terminated.
"""

import multiprocessing
import os
import signal
import time
from queue import Queue

import psutil

from skyshift.api_client import ClusterAPI
from skyshift.api_client.object_api import APIException
from skyshift.cluster_lookup import (lookup_kube_config, lookup_ray_config,
                                     lookup_slurm_config)
from skyshift.controllers import Controller, controller_error_handler
from skyshift.controllers.controller_utils import create_controller_logger
from skyshift.globals import SKYCONF_DIR
from skyshift.skylet.skylet import launch_skylet
from skyshift.structs import Informer
from skyshift.templates import Cluster, ClusterStatusEnum
from skyshift.templates.event_template import WatchEventEnum

SKYLET_CONTROLLER_INTERVAL = 0.5  # seconds


def terminate_process(pid: int):
    """Terminates a process and all its children."""
    parent = psutil.Process(pid)
    for child in parent.children(recursive=True):
        os.kill(child.pid, signal.SIGKILL)
    os.kill(parent.pid, signal.SIGKILL)


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
        self.cluster_informer: Informer = Informer(ClusterAPI(),
                                                   logger=self.logger)

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
        if event_type == WatchEventEnum.UPDATE.value and cluster_obj.get_status(
        ) == ClusterStatusEnum.READY:
            if cluster_name not in self.skylets:
                self._launch_skylet(cluster_obj)
                self.logger.info('Launched Skylet for cluster: %s.',
                                 cluster_name)
        elif event_type == WatchEventEnum.DELETE.value:
            # Terminate Skylet controllers if the cluster is deleted.
            self._terminate_skylet(cluster_obj)
            self.logger.info("Terminated Skylet for cluster: %s.",
                             cluster_name)

    def _load_clusters(self):
        k8_clusters = lookup_kube_config(self.cluster_api)
        slurm_clusters = lookup_slurm_config(self.cluster_api)
        ray_clusters = lookup_ray_config(self.cluster_api)
        new_clusters = k8_clusters + slurm_clusters + ray_clusters
        self.logger.info("Found new clusters: %s.", new_clusters)

        # Start new clusters that are detected in the configuration files.
        for cluster_dictionary in new_clusters:
            try:
                cluster_obj = ClusterAPI().create(config=cluster_dictionary)
                self._launch_skylet(cluster_obj)
            except APIException as error:
                self.logger.error("Failed to create cluster: %s. Error: %s",
                                  cluster_dictionary['metadata']['name'],
                                  error)

        # Start clusters already stored in ETCD by SkyShift.
        for cluster in self.cluster_api.list().objects:
            self._launch_skylet(cluster)

    def _launch_skylet(self, cluster_obj: Cluster):
        """Hidden method that launches Skylet in a Python thread."""
        cluster_name = cluster_obj.get_name()
        if cluster_name in self.skylets:
            self.logger.warning("Skylet already running for cluster: %s.", )
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
