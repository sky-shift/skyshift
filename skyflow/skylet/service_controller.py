"""
Service controller.
"""

import logging
import time
import traceback
from contextlib import contextmanager
from copy import deepcopy

import requests

from skyflow.api_client import ClusterAPI, ServiceAPI
from skyflow.api_client.object_api import APIException
from skyflow.cluster_manager.manager_utils import setup_cluster_manager
from skyflow.controllers import Controller
from skyflow.structs import Informer
from skyflow.templates import Service

logging.basicConfig(
    level=logging.INFO,
    format="%(name)s - %(asctime)s - %(levelname)s - %(message)s")

DEFAULT_HEARTBEAT_TIME = 3
DEFAULT_RETRY_LIMIT = 3


@contextmanager
def heartbeat_error_handler(controller: "ServiceController"):
    """Handles different types of errors from the Skylet Controller."""
    try:
        # Yield control back to the calling block
        yield
    except requests.exceptions.ConnectionError:
        controller.logger.error(traceback.format_exc())
        controller.logger.error("Cannot connect to API server. Retrying.")
    except Exception: # pylint: disable=broad-except
        controller.logger.error(traceback.format_exc())
        controller.logger.error("Encountered unusual error. Trying again.")
        time.sleep(0.5)
        controller.retry_counter += 1

    if controller.retry_counter > controller.retry_limit:
        controller.logger.error(
            "Retry limit exceeded. Service controller is down."
        )


def update_svc(svc: Service, status: dict):
    """
    Updates the status of the service in the API server.
    """
    try:
        if "clusterIP" in status:
            svc.spec.cluster_ip = status["clusterIP"]
        if "externalIP" in status:
            svc.status.external_ip = status["externalIP"]
        ServiceAPI(namespace=svc.get_namespace()).update(
            config=svc.model_dump(mode="json"))
    except APIException:
        svc = ServiceAPI(namespace=svc.get_namespace()).get(
            name=svc.get_name())
        if "clusterIP" in status:
            svc.spec.cluster_ip = status["clusterIP"]
        if "externalIP" in status:
            svc.status.external_ip = status["externalIP"]
        ServiceAPI(namespace=svc.get_namespace()).update(
            config=svc.model_dump(mode="json"))

class ServiceController(Controller): # pylint: disable=too-many-instance-attributes
    """
    Tracks the status of services in the cluster.
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
        cluster_obj = ClusterAPI().get(name)
        self.manager_api = setup_cluster_manager(cluster_obj)
        # Fetch cluster state template (cached cluster state).
        self.service_status = self.manager_api.get_service_status()
        self.informer = Informer(ServiceAPI(namespace=None))
        self.logger = logging.getLogger(f"[{self.name} - Job Controller]")
        self.logger.setLevel(logging.INFO)

    def post_init_hook(self):
        # Keeps track of cached job state.
        self.informer.start()

    def run(self):
        self.logger.info(
            "Running job controller - Updates the status of the jobs sent by Sky Manager."
        )
        while True:
            start = time.time()
            with heartbeat_error_handler(self):
                self.controller_loop()
            end = time.time()
            if end - start < self.heartbeat_interval:
                time.sleep(self.heartbeat_interval - (end - start))

    def controller_loop(self):
        self.service_status = self.manager_api.get_service_status()
        # Copy Informer cache to get the jobs stored in API server.)
        informer_object = self.informer.get_cache()
        prev_svcs = list(informer_object.keys())
        for svc_name, fetched_status in self.service_status.items():
            # For jobs that have been submitted to the cluster but do not appear on Sky Manager.
            if svc_name not in prev_svcs:
                continue
            cached_svc = deepcopy(self.informer.get_cache()[svc_name])
            update_svc(cached_svc, fetched_status)


# Testing purposes.
if __name__ == "__main__":
    jc = ServiceController("mluo-onprem")
    jc.start()
