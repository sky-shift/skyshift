"""
Service controller.
"""

import time
import traceback
from contextlib import contextmanager
from copy import deepcopy

import requests

from skyflow import utils
from skyflow.api_client import ServiceAPI
from skyflow.api_client.object_api import APIException
from skyflow.cluster_manager.manager_utils import setup_cluster_manager
from skyflow.controllers import Controller
from skyflow.controllers.controller_utils import create_controller_logger
from skyflow.globals import cluster_dir
from skyflow.structs import Informer
from skyflow.templates import Service
from skyflow.templates.cluster_template import Cluster

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
    except Exception:  # pylint: disable=broad-except
        controller.logger.error(traceback.format_exc())
        controller.logger.error("Encountered unusual error. Trying again.")
        time.sleep(0.5)
        controller.retry_counter += 1

    if controller.retry_counter > controller.retry_limit:
        controller.logger.error(
            "Retry limit exceeded. Service controller is down.")


def update_svc(svc: Service, status: dict):
    """
    Updates the status of the service in the API server.
    """
    try:
        if "clusterIP" in status:
            svc.spec.cluster_ip = status["clusterIP"]
        if "externalIP" in status:
            svc.status.external_ip = status["externalIP"]
        ServiceAPI(namespace=svc.get_namespace()).update(config=svc.model_dump(
            mode="json"))
    except APIException:
        svc = ServiceAPI(namespace=svc.get_namespace()).get(
            name=svc.get_name())
        if "clusterIP" in status:
            svc.spec.cluster_ip = status["clusterIP"]
        if "externalIP" in status:
            svc.status.external_ip = status["externalIP"]
        ServiceAPI(namespace=svc.get_namespace()).update(config=svc.model_dump(
            mode="json"))


class ServiceController(Controller):  # pylint: disable=too-many-instance-attributes
    """
    Tracks the status of services in the cluster.
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
        self.manager_api = setup_cluster_manager(cluster)
        # Fetch cluster state template (cached cluster state).
        self.logger = create_controller_logger(
            title=
            f"[{utils.unsanitize_cluster_name(self.name)} - Service Controller]",
            log_path=f'{cluster_dir(self.name)}/logs/service_controller.log')
        self.service_status = self.manager_api.get_service_status()
        self.informer = Informer(ServiceAPI(namespace=''), logger=self.logger)

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
