"""
Proxy Controller - Exposes services to other clusters.
"""
import traceback
from contextlib import contextmanager
from queue import Queue
from typing import List

import requests

from skyflow.api_client import ClusterAPI, EndpointsAPI, ServiceAPI
from skyflow.cluster_manager.manager_utils import setup_cluster_manager
from skyflow.controllers import Controller
from skyflow.controllers.controller_utils import create_controller_logger
from skyflow.globals import cluster_dir
from skyflow.network.cluster_linkv2 import (delete_export_service,
                                            delete_import_service,
                                            export_service, import_service)
from skyflow.structs import Informer
from skyflow.templates import Endpoints, WatchEventEnum


@contextmanager
def proxy_error_handler(controller: Controller):
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

        self.logger = create_controller_logger(
            title=f"[{self.name} - Proxy Controller]",
            log_path=f'{cluster_dir(self.name)}/logs/proxy_controller.log')

        self.service_informer = Informer(ServiceAPI(namespace=''),
                                         logger=self.logger)
        self.endpoints_informer = Informer(EndpointsAPI(namespace=''),
                                           logger=self.logger)

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
                # Delete the K8 endpoints object and delete import of service.
                self.manager_api.delete_endpoint_slice(event_object)
                self._delete_import_service(event_object)
            else:
                # Delete clusterlink export of service (but do not delete link).
                if self.name in event_object.spec.endpoints:
                    self._delete_export_service(event_object.get_name())
        elif event_key == WatchEventEnum.UPDATE:
            service_obj = self.service_informer.get_cache()[
                event_object.metadata.name]
            # The primary cluster imports the service and
            # creates a k8 endpoints object and attaches it to the remote service.
            if self.name == primary_cluster:
                self.logger.info("Setting up to import service from %s",
                                 primary_cluster)
                self._import_service(event_object,
                                     [a.port for a in service_obj.spec.ports])
            else:
                # Secondary clusters simply export the service.
                if self.name in event_object.spec.endpoints:
                    if not event_object.spec.endpoints[
                            self.name].exposed_to_cluster:
                        self._export_service(
                            event_object.get_name(),
                            [a.port for a in service_obj.spec.ports])
                        event_object.spec.endpoints[
                            self.name].exposed_to_cluster = True
                        EndpointsAPI(
                            namespace=event_object.get_namespace()).update(
                                config=event_object.model_dump(mode='json'))

    def _import_service(self, endpoints: Endpoints, ports: List[int]):
        name = endpoints.get_name()
        for cluster_name, endpoint_obj in endpoints.spec.endpoints.items():
            if cluster_name != endpoints.spec.primary_cluster:
                if endpoint_obj.exposed_to_cluster:
                    self.logger.info(
                        "%s is now exported by cluster, and ready to be imported",
                        name)
                    if import_service(f'{name}', self.manager_api,
                                      cluster_name, ports):
                        self.manager_api.create_endpoint_slice(
                            name, cluster_name, endpoint_obj)

    def _delete_import_service(self, endpoints: Endpoints):
        name = endpoints.get_name()
        for cluster_name, endpoint_obj in endpoints.spec.endpoints.items():
            if cluster_name != endpoints.spec.primary_cluster:
                if endpoint_obj.exposed_to_cluster:
                    self.logger.info("Deleting import of %s", name)
                    delete_import_service(f'{name}', self.manager_api,
                                          cluster_name)

    def _export_service(self, name: str, ports: List[int]):
        export_service(f'{name}', self.manager_api, ports)

    def _delete_export_service(self, name: str):
        delete_export_service(f'{name}', self.manager_api)


if __name__ == "__main__":
    jc = ProxyController("mluo-onprem")
    jc1 = ProxyController("mluo-cloud")

    jc.start()
    jc1.start()
