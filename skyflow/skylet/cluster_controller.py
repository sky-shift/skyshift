"""
Cluster controller tracks the state of the cluster.

This includes total cluster capacity, allocatable cluster capacity.
These controllers are launched in Skylet.
"""

import logging
import time
import traceback
from contextlib import contextmanager

import requests

from skyflow.api_client import ClusterAPI
from skyflow.cluster_manager.manager_utils import setup_cluster_manager
from skyflow.controllers import Controller
from skyflow.templates.cluster_template import ClusterStatus, ClusterStatusEnum

logging.basicConfig(
    level=logging.INFO,
    format="%(name)s - %(asctime)s - %(levelname)s - %(message)s")

DEFAULT_HEARTBEAT_TIME = 5
DEFAULT_RETRY_LIMIT = 5


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
        self.logger = logging.getLogger(f"[{self.name} - Cluster Controller]")
        self.logger.info("Initializing Cluster Controller: %s", self.name)

        cluster_obj = ClusterAPI().get(name)
        # The Compataibility layer that interfaces with the underlying cluster manager.
        # For now, we only support Kubernetes. (Slurm TODO)
        self.manager_api = setup_cluster_manager(cluster_obj)
        # Fetch the accelerator types on the cluster.
        # This is used to determine node affinity for jobs that
        # request specific accelerators such as T4 GPU.
        try:
            self.accelerator_types = self.manager_api.get_accelerator_types()
        except Exception: # pylint: disable=broad-except #TODO(acuadron): Add specific exception
            self.logger.error("Failed to fetch accelerator types.")
            self.update_unhealthy_cluster()
        
        self.logger.setLevel(logging.INFO)

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
        cluster_status = self.manager_api.get_cluster_status()
        if cluster_status.status == ClusterStatusEnum.ERROR.value:
            self.update_unhealthy_cluster()
            return
        self.update_healthy_cluster(cluster_status)
        self.logger.info("Updated cluster state.")

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
        # status to ERROR in the API server.
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
