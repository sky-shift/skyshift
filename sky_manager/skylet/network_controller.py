"""
The Network controller ensures that the cluster link software is healthy and running on the corresponding cluster.
"""
from contextlib import contextmanager
import logging
import requests
import time

import traceback

from sky_manager.utils import load_object
from sky_manager.controllers import Controller
from sky_manager.templates.job_template import Job, JobStatusEnum
from sky_manager.templates.cluster_template import Cluster, ClusterStatus, ClusterStatusEnum
from sky_manager.utils.utils import setup_cluster_manager
from sky_manager.structs import Informer
from sky_manager.api_client import *
from sky_manager.network.cluster_link import launch_network, status_network
logging.basicConfig(
    level=logging.INFO,
    format='%(name)s - %(asctime)s - %(levelname)s - %(message)s')


DEFAULT_HEARTBEAT_TIME = 1
DEFAULT_RETRY_LIMIT = 5

@contextmanager
def HeartbeatErrorHandler(controller: Controller):
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
        controller.update_network_state(False)
        controller.logger.error('Cluster link software failed to install correctly.')
        controller.retry_counter += 1
    
    if controller.retry_counter > controller.retry_limit:
        controller.update_network_state(False)
        controller.logger.error(f'Retry limit exceeded. Shutting down controller.')
        raise Exception('Retry limit exceeded.')

class NetworkController(Controller):
    """
    Ensure that the cluster has the network link software installed and running. If it is deleted, it will reinstall automatically.
    """
    def __init__(self, name, heartbeat_interval: int = DEFAULT_HEARTBEAT_TIME, retry_limit: int = DEFAULT_RETRY_LIMIT):
        super().__init__()

        self.name = name
        self.heartbeat_interval = heartbeat_interval
        self.retry_limit = retry_limit

        self.cluster_api = ClusterAPI()
        cluster_obj = self.cluster_api.get(name)
        # The Compataibility layer that interfaces with the underlying cluster manager.
        # For now, we only support Kubernetes. (Slurm @TODO(daron))
        self.manager_api = setup_cluster_manager(cluster_obj)

        self.logger = logging.getLogger(
            f'[{self.name} - Network Controller]')
        self.logger.setLevel(logging.INFO)

    def run(self):
        self.logger.info(
            'Running network controller - Automatically installs cluster dependencies.')
        self.retry_counter = 0
        while True:
            start = time.time()
            with HeartbeatErrorHandler(self):
                self.controller_loop()
            end = time.time()
            if end - start < self.heartbeat_interval:
                time.sleep(self.heartbeat_interval - (end - start))
    
    def controller_loop(self):
        # Install Skupper on the cluster.
        if not status_network(self.manager_api):
            self.logger.info('Installing cluster link software.')
            launch_network(self.manager_api)
        self.update_network_state(True)
    
    def update_network_state(self, state):
        cluster_obj = self.cluster_api.get(self.name)
        if cluster_obj.status.network_enabled != state:
            cluster_obj.status.network_enabled = state
            self.cluster_api.update(cluster_obj.model_dump(mode='json'))       


# Testing purposes.
if __name__ == '__main__':
    cluster_api = ClusterAPI()
    try:
        cluster_api.create(
            {
                "kind": "Cluster",
                "metadata": {
                    "name": "mluo-onprem"
                },
                "spec": {
                    'manager': 'k8',
                }
            }
        )
    except:
        pass
    hc = NetworkController('mluo-onprem')
    hc.run()