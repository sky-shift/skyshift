"""
The Network controller ensures that the cluster link software is
healthy and runs on the corresponding cluster.
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
from skyflow.network.cluster_linkv2 import launch_clusterlink, status_network

# Check every 5 minutes. Can adjust as needed.
DEFAULT_HEARTBEAT_TIME = 300
DEFAULT_RETRY_LIMIT = 5


@contextmanager
def heartbeat_error_handler(controller: "NetworkController"):
    """Handles different types of errors from the Skylet Controller."""
    try:
        # Yield control back to the calling block
        yield
    except requests.exceptions.ConnectionError:
        controller.logger.error(traceback.format_exc())
        controller.logger.error("Cannot connect to API server. Retrying.")
    except Exception:  # pylint: disable=broad-except
        controller.logger.error(traceback.format_exc())
        controller.update_network_state(False)
        controller.logger.error(
            "Cluster link software failed to install correctly.")
        controller.retry_counter += 1

    if controller.retry_counter > controller.retry_limit:
        controller.update_network_state(False)
        controller.logger.error(
            "Retry limit exceeded. Shutting down controller.")
        raise Exception("Retry limit exceeded.")


class NetworkController(Controller):
    """
    Ensure that the cluster has the network link software installed and running.
    If it is deleted, it will reinstall automatically.
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
        self.cluster_api = ClusterAPI()
        cluster_obj = self.cluster_api.get(name)
        self.logger = create_controller_logger(
            title=f"[{utils.unsanitize_cluster_name(self.name)} - Network Controller]",
            log_path=f'{cluster_dir(self.name)}/logs/network_controller.log')
        # The Compataibility layer that interfaces with the underlying cluster manager.
        # For now, we only support Kubernetes. (Slurm @TODO(daron))
        self.manager_api = setup_cluster_manager(cluster_obj)

    def run(self):
        self.logger.info(
            "Running network controller - Automatically installs cluster dependencies."
        )
        while True:
            start = time.time()
            with heartbeat_error_handler(self):
                self.controller_loop()
            end = time.time()
            if end - start < self.heartbeat_interval:
                time.sleep(self.heartbeat_interval - (end - start))

    def controller_loop(self):
        # Install Skupper on the cluster.
        if not status_network(self.manager_api):
            self.logger.info('Installing clusterlink software.')
            launch_clusterlink(self.manager_api)
        self.update_network_state(True)

    def update_network_state(self, state):
        """Update the network state of the cluster."""
        cluster_obj = self.cluster_api.get(self.name)
        if cluster_obj.status.network_enabled != state:
            cluster_obj.status.network_enabled = state
            self.cluster_api.update(cluster_obj.model_dump(mode="json"))


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
#     hc = NetworkController("mluo-onprem")
#     hc.run()
