"""Provisioner Controller
"""
import threading
import time
import traceback
from contextlib import contextmanager
from queue import Queue

import psutil
import requests

from skyshift.api_client import ClusterAPI
from skyshift.api_client.object_api import APIException
from skyshift.cloud.skypilot_provisioning import (
    add_node_to_cluster, delete_kubernetes_cluster,
    provision_new_kubernetes_cluster)
from skyshift.cloud.utils import delete_unused_cluster_config
from skyshift.cluster_manager.manager_utils import setup_cluster_manager
from skyshift.controllers.controller import Controller
from skyshift.controllers.controller_utils import create_controller_logger
from skyshift.globals import SKYCONF_DIR
from skyshift.structs import Informer
from skyshift.templates import Cluster, ClusterStatusEnum
from skyshift.templates.event_template import WatchEvent, WatchEventEnum

PROVISIONER_CONTROLLER_INTERVAL = 0.5  # seconds


def terminate_process(pid: int):
    """Terminates a process and all its children."""
    parent = psutil.Process(pid)
    for child in parent.children(recursive=True):
        child.terminate()
    parent.terminate()


@contextmanager
def provisioner_controller_error_handler(controller: Controller):
    """Handles different types of errors from the Provisioner Controller."""
    try:
        # Yield control back to the calling block
        yield
    except requests.exceptions.ConnectionError:
        controller.logger.error(traceback.format_exc())
        controller.logger.error('Cannot connect to API server. Retrying.')
    except Exception:  # pylint: disable=broad-except
        controller.logger.error(traceback.format_exc())


class ProvisionerController(Controller):
    """
    Provisioner Controller - Manages provisioning of cloud clusters using SkyPilot + RKE.
    """

    def __init__(self):
        super().__init__()
        self.logger = self.logger = create_controller_logger(
            title="[Provisioner Controller]",
            log_path=f'{SKYCONF_DIR}/provisioner_controller.log')
        # Python thread safe queue for Informers to append events to.
        self.event_queue = Queue()
        self.cluster_api = ClusterAPI()
        self.cluster_informer = Informer(self.cluster_api, self.logger)

    def post_init_hook(self):
        """Declares a Cluster informer that watches all changes to all cluster objects."""

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
        self.logger.info('Executing Provisioner Controller - \
                Manages provisioning of cloud clusters using SkyPilot + RKE.')
        while True:
            with provisioner_controller_error_handler(self):
                self.controller_loop()
            # Serves as a form of rate limiting.
            time.sleep(PROVISIONER_CONTROLLER_INTERVAL)

    def controller_loop(self):
        watch_event: WatchEvent = self.event_queue.get()
        cluster_obj: Cluster = watch_event.object
        cluster_name = cluster_obj.get_name()
        self.logger.info('Cluster %s: %s', cluster_name,
                         watch_event.event_type)
        if watch_event.event_type == WatchEventEnum.ADD:
            # Launch Skylet if it is a newly added cluster.
            cluster_name = cluster_obj.get_name()
            if not cluster_obj.spec.provision:
                self.logger.info(
                    'Cluster %s has provisioning flag set to `False`, '
                    'skipping provisioning.', cluster_name)
                try:
                    setup_cluster_manager(cluster_obj)
                except Exception as error:  # pylint: disable=broad-except
                    self.logger.info(error)
                    self.update_cluster_obj_status(cluster_name,
                                                   ClusterStatusEnum.ERROR)
                else:
                    self.update_cluster_obj_status(cluster_name,
                                                   ClusterStatusEnum.READY)
                return

            try:
                self.logger.info('Provisioning cluster %s...', cluster_name)
                self.update_cluster_obj_status(cluster_name,
                                               ClusterStatusEnum.PROVISIONING)

                # Provision initial RKE2 cluster
                cluster_ip, rke2_token = provision_new_kubernetes_cluster(
                    cluster_obj=cluster_obj)
                self.update_cluster_obj_rke2_spec(cluster_name, cluster_ip,
                                                  rke2_token)

                # Provision and attach additional nodes in parallel
                threads: list[threading.Thread] = []
                for i in range(1, cluster_obj.spec.num_nodes):
                    thread = threading.Thread(target=add_node_to_cluster,
                                              args=(cluster_obj, i, cluster_ip,
                                                    rke2_token))
                    thread.start()
                    threads.append(thread)

                for thread in threads:
                    thread.join()
            except Exception as error:  # pylint: disable=broad-except
                self.logger.info(
                    'Error provisioning cluster %s.'
                    'Removing cluster resources.', cluster_name)
                self.logger.error(error)
                delete_unused_cluster_config(cluster_name)
                self.update_cluster_obj_status(cluster_name,
                                               ClusterStatusEnum.ERROR,
                                               str(error).strip())
                return
            self.update_cluster_obj_status(cluster_name,
                                           ClusterStatusEnum.READY)
        elif watch_event.event_type == WatchEventEnum.DELETE and cluster_obj.spec.provision:
            self.logger.info('Terminating cluster %s...', cluster_name)
            delete_unused_cluster_config(cluster_name)
            delete_kubernetes_cluster(cluster_name, cluster_obj.spec.num_nodes)

    def update_cluster_obj_status(self,
                                  cluster_name: str,
                                  status: ClusterStatusEnum,
                                  error_message: str = "",
                                  retry_limit: int = 5):
        """Updates the status of a cluster object."""

        def _update_cluster_obj_status(cluster_name: str,
                                       status: ClusterStatusEnum):
            cluster_obj: Cluster = self.cluster_api.get(cluster_name)
            cluster_obj.status.update_status(status.value)
            cluster_obj.status.update_error_message(error_message)
            self.cluster_api.update(cluster_obj.model_dump(mode='json'))

        for _ in range(retry_limit):
            try:
                _update_cluster_obj_status(cluster_name, status)
                return
            except APIException:
                pass
        _update_cluster_obj_status(cluster_name, ClusterStatusEnum.ERROR)

    def update_cluster_obj_rke2_spec(self,
                                     cluster_name: str,
                                     rke2_ip: str,
                                     rke2_token: str,
                                     retry_limit: int = 5):
        """Updates the status of a cluster object."""

        def _update_cluster_obj_rke2_spec(cluster_name: str, rke2_ip: str,
                                          rke2_token: str):
            cluster_obj: Cluster = self.cluster_api.get(cluster_name)
            cluster_obj.spec.access_config["rke2_ip"] = rke2_ip
            cluster_obj.spec.access_config["rke2_token"] = rke2_token
            self.cluster_api.update(cluster_obj.model_dump(mode='json'))

        for _ in range(retry_limit):
            try:
                _update_cluster_obj_rke2_spec(cluster_name, rke2_ip,
                                              rke2_token)
                return
            except APIException:
                pass
        self.update_cluster_obj_status(cluster_name, ClusterStatusEnum.ERROR)


# Testing purposes.
if __name__ == '__main__':
    cont = ProvisionerController()
    cont.run()
