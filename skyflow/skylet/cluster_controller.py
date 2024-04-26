"""
Cluster controller tracks the state of the cluster.

This includes total cluster capacity, allocatable cluster capacity.
These controllers are launched in Skylet.
"""

import time
import traceback
from contextlib import contextmanager

import requests

from skyflow import utils
from skyflow.api_client import ClusterAPI
from skyflow.cluster_manager.manager_utils import setup_cluster_manager
from skyflow.controllers import Controller
from skyflow.controllers.controller_utils import create_controller_logger
from skyflow.globals import cluster_dir
from skyflow.templates.cluster_template import ClusterStatus, ClusterStatusEnum

DEFAULT_HEARTBEAT_TIME = 5  # seconds
DEFAULT_RETRY_LIMIT = 2  # seconds


@contextmanager
def heartbeat_error_handler(controller: "ClusterController"):
    """Handles different types of errors from the Skylet Controller."""
    try:
        # Yield control back to the calling block
        yield
    except requests.exceptions.ConnectionError:
        controller.logger.error(traceback.format_exc())
        controller.logger.error("Cannot connect to API server. Retrying.")
    except Exception:  # pylint: disable=broad-except
        controller.logger.error(traceback.format_exc())
        controller.logger.error("Encountered unusual error. Trying again.")
        controller.retry_counter += 1

    if controller.retry_counter > controller.retry_limit:
        controller.logger.error(
            f"Retry limit exceeded. Marking cluster {controller.name} as ERROR state."
        )
        controller.update_unhealthy_cluster()


class ClusterController(Controller):
    """
    Regularly polls the cluster for its status and updates the API server of
    the latest status.

    The status includes the cluster capacity, allocatable capacity, and the
    current status of the cluster.
    """

    def __init__(
        self,
        name,
        heartbeat_interval: int = DEFAULT_HEARTBEAT_TIME,
        retry_limit: int = DEFAULT_RETRY_LIMIT,
    ):
        super().__init__()

        self.name = name
        self.heartbeat_interval = heartbeat_interval
        self.retry_limit = retry_limit
        self.retry_counter = 0
        self.logger = create_controller_logger(
            title=
            f"[{utils.unsanitize_cluster_name(self.name)} - Cluster Controller]",
            log_path=f'{cluster_dir(self.name)}/logs/cluster_controller.log')

        self.logger.info("Initializing Cluster Controller: %s", self.name)
        cluster_obj = ClusterAPI().get(name)
        # The Compataibility layer that interfaces with the underlying cluster manager.
        # For now, we only support Kubernetes. (Slurm TODO)
        self.manager_api = setup_cluster_manager(cluster_obj)
        # Fetch the accelerator types on the cluster.
        # This is used to determine node affinity for jobs that
        # request specific accelerators such as T4 GPU.
        # @TODO(acuadron): Add specific exception
        try:
            self.accelerator_types = self.manager_api.get_accelerator_types()
        except Exception:  # pylint: disable=broad-except
            self.logger.error("Failed to fetch accelerator types.")
            self.update_unhealthy_cluster()

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
            return
        self.update_healthy_cluster(cluster_status)
        self.logger.debug("Updated cluster state.")

    def update_healthy_cluster(self, cluster_status: ClusterStatus):
        """Updates the healthy cluster status (READY)."""
        cluster_api = ClusterAPI()
        cluster_obj = cluster_api.get(self.name)
        prev_cluster_status = cluster_obj.status
        prev_cluster_status.update_status(cluster_status.status)
        prev_cluster_status.update_capacity(cluster_status.capacity)
        prev_cluster_status.update_allocatable_capacity(
            cluster_status.allocatable_capacity)
        cluster_api.update(cluster_obj.model_dump(mode="json"))

    def update_unhealthy_cluster(self):
        """Updates the unhealthy cluster status (ERROR)."""
        # When the cluster is unhealthy, we need to update the cluster
        # status to ERROR in the API server. But not kill the skylet
        # (maybe it reestablishes connection later)
        cluster_api = ClusterAPI()
        cluster_obj = cluster_api.get(self.name)
        cluster_status = cluster_obj.status
        cluster_status.update_status(ClusterStatusEnum.ERROR.value)
        cluster_api.update(cluster_obj.model_dump(mode="json"))


# Testing purposes.
# if __name__ == "__main__":
#     cluster_api = ClusterAPI()
#     try:
#         cluster_api.create({
#             "kind": "Cluster",
#             "metadata": {
#                 "name": "mluo-onprem"
#             },
#             "spec": {
#                 "manager": "k8",
#             },
#         })
#     except:
#         pass
#     hc = ClusterController("mluo-onprem")
#     hc.run()
