"""
Cluster controller tracks the state of the cluster.

This includes total cluster capacity, allocatable cluster capacity.
These controllers are launched in Skylet.
"""

import time
from contextlib import contextmanager

import requests

from skyshift import utils
from skyshift.api_client import ClusterAPI
from skyshift.cluster_manager.manager_utils import setup_cluster_manager
from skyshift.controllers import Controller
from skyshift.controllers.controller_utils import create_controller_logger
from skyshift.globals import cluster_dir
from skyshift.templates.cluster_template import (Cluster, ClusterStatus,
                                                 ClusterStatusEnum)

DEFAULT_HEARTBEAT_TIME = 5  # seconds
DEFAULT_RETRY_LIMIT = 5  # attempts


@contextmanager
def heartbeat_error_handler(controller: "ClusterController"):
    """Handles different types of errors from the Skylet Controller."""
    try:
        # Yield control back to the calling block
        yield
    except requests.exceptions.Timeout:
        controller.logger.error("Request timed out. Retrying.")
        # Keep track of the number of retries for each failed attempt.
        controller.retry_counter += 1
    except requests.exceptions.ConnectionError:
        controller.logger.error("Cannot connect to API server. Retrying.")
        # Keep track of the number of retries for each failed attempt.
        controller.retry_counter += 1
    except Exception:  # pylint: disable=broad-except
        controller.logger.error("Encountered unusual error. Trying again.")
        # Keep track of the number of retries for each failed attempt.
        controller.retry_counter += 1

    if controller.retry_counter > controller.retry_limit:
        controller.logger.error(
            f"Retry limit exceeded. Marking cluster {controller.name} as ERROR state."
        )
        controller.update_unhealthy_cluster()


class ClusterController(Controller):  # pylint: disable=too-many-instance-attributes
    """
    Regularly polls the cluster for its status and updates the API server of
    the latest status.

    The status includes the cluster capacity, allocatable capacity, and the
    current status of the cluster.
    """

    def __init__(
        self,
        cluster: Cluster,
        heartbeat_interval: int = DEFAULT_HEARTBEAT_TIME,
        retry_limit: int = DEFAULT_RETRY_LIMIT,
    ):
        super().__init__(cluster)

        self.name = cluster.get_name()
        self.heartbeat_interval = heartbeat_interval
        self.retry_limit = retry_limit
        self.retry_counter = 0
        self.logger = create_controller_logger(
            title=
            f"[{utils.unsanitize_cluster_name(self.name)} - Cluster Controller]",
            log_path=f'{cluster_dir(self.name)}/logs/cluster_controller.log')

        self.logger.info("Initializing Cluster Controller: %s", self.name)
        self.cluster_api = ClusterAPI()
        self.cluster_obj = cluster
        # The Compataibility layer that interfaces with the underlying cluster manager.
        self.manager_api = setup_cluster_manager(self.cluster_obj)

    def run(self):
        self.logger.info(
            "Running cluster controller - Updates the state of the cluster.")
        while True:
            start = time.time()
            with heartbeat_error_handler(self):
                self.controller_loop()
            end = time.time()
            if end - start < self.heartbeat_interval:
                time.sleep(self.heartbeat_interval - (end - start))

    def controller_loop(self):
        """Main loop for the Cluster Controller. Updates the cluster state."""
        cluster_status = self.manager_api.get_cluster_status()
        if cluster_status.status == ClusterStatusEnum.ERROR.value:
            self.update_unhealthy_cluster()
        else:
            self.update_healthy_cluster(cluster_status)
            self.logger.debug("Updated cluster state.")

    def update_healthy_cluster(self, cluster_status: ClusterStatus):
        """Updates the healthy cluster status (READY)."""
        self.cluster_obj = self.cluster_api.get(self.name)
        prev_cluster_status = self.cluster_obj.status
        prev_cluster_status.update_status(cluster_status.status)
        prev_cluster_status.update_capacity(cluster_status.capacity)
        prev_cluster_status.update_allocatable_capacity(
            cluster_status.allocatable_capacity)
        self.cluster_api.update(self.cluster_obj.model_dump(mode="json"))

    def update_unhealthy_cluster(self):
        """Updates the unhealthy cluster status (ERROR)."""
        # When the cluster is unhealthy, we need to update the cluster
        # status to ERROR in the API server. But not kill the skylet
        # (maybe it reestablishes connection later)
        self.cluster_obj = self.cluster_api.get(self.name)
        cluster_status = self.cluster_obj.status
        cluster_status.update_status(ClusterStatusEnum.ERROR.value)
        self.cluster_api.update(self.cluster_obj.model_dump(mode="json"))
