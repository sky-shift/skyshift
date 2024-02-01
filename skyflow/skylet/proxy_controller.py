"""
Proxy Controller - Exposes services to other clusters.
"""
import logging
import traceback
from contextlib import contextmanager
from queue import Queue
from typing import List

import requests

from skyflow.api_client import ClusterAPI, EndpointsAPI, ServiceAPI
from skyflow.cluster_manager.manager_utils import setup_cluster_manager
from skyflow.controllers import Controller
from skyflow.network.cluster_link import expose_service, unexpose_service
from skyflow.structs import Informer
from skyflow.templates import WatchEventEnum

logging.basicConfig(
    level=logging.INFO,
    format="%(name)s - %(asctime)s - %(levelname)s - %(message)s")


@contextmanager
def proxy_error_handler(controller: Controller):
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


class ProxyController(Controller):
    """
    The Proxy controller establishes links between different clusters.
    """

    def __init__(self, name) -> None:
        super().__init__()
        self.name = name
        cluster_obj = ClusterAPI().get(name)
        self.manager_api = setup_cluster_manager(cluster_obj)
        self.worker_queue: Queue = Queue()

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        self.service_informer = Informer(ServiceAPI(namespace=None))
        self.endpoints_informer = Informer(EndpointsAPI(namespace=None))

        self.logger = logging.getLogger(f"[{self.name} - Proxy Controller]")
        self.logger.setLevel(logging.INFO)

    def post_init_hook(self):
        def update_callback_fn(old_obj, event):
            new_obj = event.object
            old_obj_endpoints = old_obj.spec.endpoints
            new_obj_endpoints = new_obj.spec.endpoints
            if self.name == event.object.spec.primary_cluster:
                self.worker_queue.put(event)
                return
            # Trigger when an endpoint has been created, deleted or changed.
            if self.name in old_obj_endpoints and self.name not in new_obj_endpoints:
                # An endpoint has been deleted
                self.worker_queue.put(event)
            elif self.name not in old_obj_endpoints and self.name in new_obj_endpoints:
                # An endpoint has been created
                self.worker_queue.put(event)
            elif self.name in old_obj_endpoints and self.name in new_obj_endpoints:
                # Number of endpoints has changed.
                if (old_obj_endpoints[self.name].num_endpoints !=
                        new_obj_endpoints[self.name].num_endpoints or
                        not new_obj_endpoints[self.name].exposed_to_cluster):
                    self.worker_queue.put(event)

        def delete_callback_fn(event):
            self.worker_queue.put(event)

        self.endpoints_informer.add_event_callbacks(
            update_event_callback=update_callback_fn,
            delete_event_callback=delete_callback_fn,
        )
        self.endpoints_informer.start()
        self.service_informer.start()

    def run(self):
        self.logger.info(
            "Running proxy controller - it exposes services to other clusters."
        )
        while True:
            with proxy_error_handler(self):
                self.controller_loop()

    def controller_loop(self):
        # Poll for jobs and execute/kill them depending on the job status.
        # Blocks until there is at least 1 element in the queue.
        event = self.worker_queue.get()
        event_key = event.event_type
        event_object = event.object

        primary_cluster = event_object.spec.primary_cluster
        if event_key == WatchEventEnum.DELETE:
            if self.name == primary_cluster:
                # Delete the K8 endpoints object.
                self.manager_api.delete_endpoint_slice(event_object)
            else:
                # Delete skupper expose (but do not delete link).
                if self.name in event_object.spec.endpoints:
                    self._unexpose_service(event_object.get_name())
        elif event_key == WatchEventEnum.UPDATE:
            service_obj = self.service_informer.get_cache()[
                event_object.metadata.name]
            # The primary cluster creates a k8 endpoints object and attaches it to the service.
            print(self.name, primary_cluster)
            if self.name == primary_cluster:
                self.manager_api.create_or_update_endpoint_slice(event_object)
            else:
                # Secondary clusters simply expose the service.
                if self.name not in event_object.spec.endpoints:
                    self._unexpose_service(event_object.get_name())
                else:
                    if not event_object.spec.endpoints[
                            self.name].exposed_to_cluster:
                        self._expose_service(
                            event_object.get_name(),
                            [a.port for a in service_obj.spec.ports],
                        )
                        event_object.spec.endpoints[
                            self.name].exposed_to_cluster = True
                        EndpointsAPI(
                            namespace=event_object.get_namespace()).update(
                                config=event_object.model_dump(mode="json"))

    def _expose_service(self, name: str, ports: List[int]):
        expose_service(f"{name}", self.manager_api, ports)

    def _unexpose_service(self, name: str):
        unexpose_service(f"{name}", self.manager_api)


if __name__ == "__main__":
    jc = ProxyController("mluo-onprem")
    jc1 = ProxyController("mluo-cloud")

    jc.start()
    jc1.start()
