"""
Source code for the log controllers that keep track of the state of the cluster and jobs. These controllers are launched in Skylet.
"""

import logging
import time
import traceback
from contextlib import contextmanager
from copy import deepcopy

import requests

from skyflow.api_client import *
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
def HeartbeatErrorHandler(controller: "ServiceController"):
    """Handles different types of errors from the Skylet Controller."""
    try:
        # Yield control back to the calling block
        yield
    except requests.exceptions.ConnectionError as e:
        controller.logger.error(traceback.format_exc())
        controller.logger.error("Cannot connect to API server. Retrying.")
    except Exception as e:
        controller.logger.error(traceback.format_exc())
        controller.logger.error("Encountered unusual error. Trying again.")
        time.sleep(0.5)
        controller.retry_counter += 1

    if controller.retry_counter > controller.retry_limit:
        controller.logger.error(
            f"Retry limit exceeded. Marking pending/running jobs in ERROR state."
        )


class ServiceController(Controller):

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

        cluster_obj = ClusterAPI().get(name)
        self.manager_api = setup_cluster_manager(cluster_obj)
        # Fetch cluster state template (cached cluster state).
        self.service_status = self.manager_api.get_service_status()

        self.logger = logging.getLogger(f"[{self.name} - Job Controller]")
        self.logger.setLevel(logging.INFO)

    def post_init_hook(self):
        # Keeps track of cached job state.
        self.informer = Informer(ServiceAPI(namespace=None))
        self.informer.start()

    def run(self):
        self.logger.info(
            "Running job controller - Updates the status of the jobs sent by Sky Manager."
        )
        self.retry_counter = 0
        while True:
            start = time.time()
            with HeartbeatErrorHandler(self):
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
            else:
                cached_svc = deepcopy(self.informer.get_cache()[svc_name])
            self.update_svc(cached_svc, fetched_status)

    def update_svc(self, svc: Service, status: dict):
        try:
            if "clusterIP" in status:
                svc.spec.cluster_ip = status["clusterIP"]
            if "externalIP" in status:
                svc.status.external_ip = status["externalIP"]
            ServiceAPI(namespace=svc.get_namespace()).update(
                config=svc.model_dump(mode="json"))
        except:
            svc = ServiceAPI(namespace=svc.get_namespace()).get(
                name=svc.get_name())
            if "clusterIP" in status:
                svc.spec.cluster_ip = status["clusterIP"]
            if "externalIP" in status:
                svc.status.external_ip = status["externalIP"]
            ServiceAPI(namespace=svc.get_namespace()).update(
                config=svc.model_dump(mode="json"))


# Testing purposes.
if __name__ == "__main__":
    jc = ServiceController("mluo-onprem")
    jc.start()
