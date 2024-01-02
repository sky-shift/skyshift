from contextlib import contextmanager
from copy import deepcopy
from queue import Queue
import logging
import requests
import traceback
import time
import uuid

from skyflow.structs import Informer
from skyflow.controllers import Controller
from skyflow.utils.utils import setup_cluster_manager
from skyflow.templates import Service, Job, WatchEventEnum, EndpointObject, Endpoints
from skyflow.api_client import *
from skyflow.utils import match_labels

logging.basicConfig(
    level=logging.INFO,
    format='%(name)s - %(asctime)s - %(levelname)s - %(message)s')

@contextmanager
def EndpointsErrorHandler(controller: Controller):
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
        controller.logger.error('Encountered unusual error. Trying again.')

class EndpointsController(Controller):
    """
    The Endpoints controller keeps track of the endpoints of services in the cluster.
    """
    def __init__(self, name) -> None:
        super().__init__()
        self.name = name
        cluster_obj = ClusterAPI().get(name)
        self.manager_api = setup_cluster_manager(cluster_obj)
        self.worker_queue = Queue()

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        self.logger = logging.getLogger(
            f'[{self.name} - Endpoints Controller]')
        self.logger.setLevel(logging.INFO)

    def post_init_hook(self):
        # # Python thread safe queue for Informers to append events to.
        # self.job_informer = Informer(JobAPI(namespace=None))

        # def update_callback_fn(event):
        #     event_object = event.object
        #     # Filter for jobs that are scheduled by the Scheduler Controller and
        #     # are assigned to this cluster.
        #     if self.name in event_object.status.replica_status:
        #         if self.name not in event_object.status.job_ids:
        #             self.worker_queue.put(event)

        # def delete_callback_fn(event):
        #     event_object = event.object
        #     if self.name in event_object.status.replica_status:
        #         self.worker_queue.put(event)

        # Filtered add events and delete events are added to the worker queue.
        # self.job_informer.add_event_callbacks(
        #     update_event_callback=update_callback_fn,
        #     delete_event_callback=delete_callback_fn)
        # self.job_informer.start()

        self.service_informer = Informer(ServiceAPI(namespace=None))

        def add_svc_callback_fn(event):
            self.worker_queue.put(event)
        
        def update_svc_callback_fn(old_obj, event):
            new_obj = event.obj
            if old_obj.spec.selector != new_obj.spec.selector:
                self.worker_queue.put(event)
            elif old_obj.spec.primary_cluster != new_obj.spec.primary_cluster:
                self.worker_queue.put(event)
        
        def delete_svc_callback_fn(event):
            self.worker_queue.put(event)

        self.service_informer.add_event_callbacks(
            add_event_callback=add_svc_callback_fn,
            update_event_callback=update_svc_callback_fn,
            delete_event_callback=delete_svc_callback_fn)
        self.service_informer.start()

    def run(self):
        self.logger.info(
            'Running endpoints controller - keeps track of jobs across clusters (for services).'
        )
        while True:
            with EndpointsErrorHandler(self):
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
            if event_key == WatchEventEnum.ADD or event_key == WatchEventEnum.UPDATE:
                end_obj = self._create_or_update_endpoint(event_object)
                try:
                    EndpointsAPI(namespace=service_namespace).update(config=end_obj.model_dump(mode='json'))
                except Exception as e:
                    self.worker_queue.put(event)
            elif event_key == WatchEventEnum.DELETE:
                # Remove the endpoint object (only the primary cluster removes it)
                if primary_cluster == self.name:
                    EndpointsAPI(namespace=service_namespace).delete(name=service_name)
                self.manager_api.delete_service(event_object)
        elif isinstance(event_object, Job):
            # Search for all services that match the added/updated/deleted job's selectors.
            pass
    
    def _create_or_update_endpoint(self, service: Service):
        service_name = service.get_name()
        service_namespace = service.get_namespace()
        primary_cluster = service.spec.primary_cluster
        all_endpoints = EndpointsAPI(namespace=service_namespace).list()
        if primary_cluster == self.name and service_name not in [e.get_name() for e in all_endpoints.objects]:
            # Create the endpoint object.
            end_obj = {
                'kind': 'Endpoints',
                'metadata': {
                    'name': service_name,
                    'namespace': service_namespace,
                },
                'spec': {
                    'primary_cluster': primary_cluster,
                }
            }
            end_obj = Endpoints(**end_obj)
            end_obj = EndpointsAPI(namespace=service_namespace).create(end_obj.model_dump(mode='json'))
            print(end_obj)
            self.manager_api.create_or_update_service(service)
        else:
            end_obj = self._retry_until_fetch_object(name=service_name, namespace=service_namespace)
        
        num_endpoints = len(self.manager_api.get_pods_with_selector(service.spec.selector).items)
        if num_endpoints > 0:
            if  self.name not in end_obj.spec.endpoints or (end_obj.spec.endpoints[self.name].num_endpoints != num_endpoints):
                if self.name not in end_obj.spec.endpoints:
                    # Create/update existing service on the cluster.
                    self.manager_api.create_or_update_service(service)
                # Get endpoint object.
                end_obj.spec.endpoints[self.name] = EndpointObject(num_endpoints=num_endpoints, exposed_to_cluster=False)
        elif num_endpoints ==0 and self.name in end_obj.spec.endpoints:
                del end_obj.spec.endpoints[self.name]
                self.manager_api.delete_service(service)
        else:
            return end_obj
        return end_obj

    
    def _retry_until_fetch_object(self, name: str, namespace: str):
        """Retries until the object is fetched."""
        retry = 0 
        while True:
            try:
                return EndpointsAPI(namespace=namespace).get(name=name)
            except Exception as e:
                retry+=1
                self.logger.error(
                    f'Could not fetch {name}. Retrying.')
                time.sleep(0.1)
                if retry == 10:
                    raise e


if __name__ == '__main__':
    jc = EndpointsController('mluo-onprem')
    jc1 = EndpointsController('mluo-cloud')

    jc.start()
    jc1.start()
