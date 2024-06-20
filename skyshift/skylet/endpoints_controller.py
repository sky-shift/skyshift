"""
Endpoints controller manages updating available endpoints over diff clusters.
"""
import queue
import time
import traceback
from contextlib import contextmanager

import requests

from skyshift import utils
from skyshift.api_client import EndpointsAPI, ServiceAPI
from skyshift.api_client.object_api import APIException
from skyshift.cluster_manager import KubernetesManager, Manager
from skyshift.cluster_manager.manager_utils import setup_cluster_manager
from skyshift.controllers import Controller
from skyshift.controllers.controller_utils import create_controller_logger
from skyshift.globals import cluster_dir
from skyshift.structs import Informer
from skyshift.templates import (EndpointObject, Endpoints, Job, Service,
                                WatchEventEnum)
from skyshift.templates.cluster_template import Cluster


def _filter_manager(manager: Manager) -> KubernetesManager:
    if isinstance(manager, KubernetesManager):
        return manager
    raise ValueError("Manager is not a KubernetesManager.")


@contextmanager
def endpoints_error_handler(controller: Controller):
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


class EndpointsController(Controller):
    """
    The Endpoints controller keeps track of the endpoints of services in the cluster.
    """

    def __init__(self, cluster: Cluster) -> None:
        super().__init__(cluster)
        self.name = cluster.get_name()
        self.cluster_obj = cluster
        self.manager_api = _filter_manager(setup_cluster_manager(cluster))
        self.worker_queue: queue.Queue = queue.Queue()

        self.logger = create_controller_logger(
            title=
            f"[{utils.unsanitize_cluster_name(self.name)} - Endpoints Controller]",
            log_path=f'{cluster_dir(self.name)}/logs/endpoints_controller.log')
        self.service_informer = Informer(ServiceAPI(namespace=''),
                                         logger=self.logger)

    def post_init_hook(self):

        def add_svc_callback_fn(event):
            self.worker_queue.put(event)

        def update_svc_callback_fn(old_obj, event):
            new_obj = event.object
            if old_obj.spec.selector != new_obj.spec.selector:
                self.worker_queue.put(event)
            elif old_obj.spec.primary_cluster != new_obj.spec.primary_cluster:
                self.worker_queue.put(event)

        def delete_svc_callback_fn(event):
            self.worker_queue.put(event)

        self.service_informer.add_event_callbacks(
            add_event_callback=add_svc_callback_fn,
            update_event_callback=update_svc_callback_fn,
            delete_event_callback=delete_svc_callback_fn,
        )
        self.service_informer.start()

    def run(self):
        self.logger.info(
            "Running endpoints controller - keeps track of jobs across clusters (for services)."
        )
        while True:
            with endpoints_error_handler(self):
                self.controller_loop()

    def controller_loop(self):
        # Poll for jobs and execute/kill them depending on the job status.
        # Blocks until there is at least 1 element in the queue.
        event = self.worker_queue.get()
        event_key = event.event_type
        event_object = event.object

        if isinstance(event_object, Service):
            service_name = event_object.get_name()
            service_namespace = event_object.get_namespace()
            primary_cluster = event_object.spec.primary_cluster
            if event_key in [WatchEventEnum.ADD, WatchEventEnum.UPDATE]:
                end_obj = self._create_or_update_endpoint(event_object)
                try:
                    EndpointsAPI(namespace=service_namespace).update(
                        config=end_obj.model_dump(mode="json"))
                except APIException:
                    self.worker_queue.put(event)
            elif event_key == WatchEventEnum.DELETE:
                # Remove the endpoint object (only the primary cluster removes it)
                if primary_cluster == self.name:
                    EndpointsAPI(namespace=service_namespace).delete(
                        name=service_name)
                self.manager_api.delete_service(event_object)
        elif isinstance(event_object, Job):
            # Search for all services that match the added/updated/deleted job's selectors.
            pass

    def _create_or_update_endpoint(self, service: Service):
        service_name = service.get_name()
        service_namespace = service.get_namespace()
        primary_cluster = service.spec.primary_cluster
        all_endpoints = EndpointsAPI(namespace=service_namespace).list()
        if primary_cluster == self.name and service_name not in [
                e.get_name() for e in all_endpoints.objects
        ]:
            # Create the endpoint object.
            end_obj_dict: dict = {
                "kind": "Endpoints",
                "metadata": {
                    "name": service_name,
                    "namespace": service_namespace,
                },
                "spec": {
                    "primary_cluster": primary_cluster,
                },
            }
            end_obj = Endpoints(**end_obj_dict)
            EndpointsAPI(namespace=service_namespace).create(
                end_obj.model_dump(mode="json"))
            self.manager_api.create_or_update_service(service)
        else:
            end_obj = self._retry_until_fetch_object(
                name=service_name, namespace=service_namespace)

        end_obj_spec = end_obj.spec
        num_endpoints = len(
            self.manager_api.get_pods_with_selector(
                service.spec.selector).items)
        if num_endpoints > 0:
            if self.name not in end_obj_spec.endpoints or (
                    end_obj_spec.endpoints[self.name].num_endpoints !=
                    num_endpoints):
                if self.name not in end_obj_spec.endpoints:
                    # Create/update existing service on the cluster.
                    self.manager_api.create_or_update_service(service)
                # Get endpoint object.
                end_obj_spec.endpoints[self.name] = EndpointObject(
                    num_endpoints=num_endpoints, exposed_to_cluster=False)
        elif num_endpoints == 0 and self.name in end_obj_spec.endpoints:
            del end_obj_spec.endpoints[self.name]
            self.manager_api.delete_service(service)
        else:
            return end_obj
        return end_obj

    def _retry_until_fetch_object(self, name: str,
                                  namespace: str) -> Endpoints:
        """Retries until the object is fetched."""
        retry = 0
        while True:
            try:
                endpoints = EndpointsAPI(namespace=namespace).get(name=name)
                return endpoints
            except APIException as error:
                retry += 1
                self.logger.error("Could not fetch %s. Retrying.", name)
                time.sleep(0.1)
                if retry == 10:
                    raise error
