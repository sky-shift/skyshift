from contextlib import contextmanager
from copy import deepcopy
from queue import Queue
import logging
import requests
import traceback
import time
import uuid

from sky_manager.structs import Informer
from sky_manager.controllers import Controller
from sky_manager.utils.utils import setup_cluster_manager
from sky_manager.templates import FilterPolicy, Job, JobStatusEnum, WatchEventEnum
from sky_manager.api_client import *
from sky_manager.utils import match_labels

logging.basicConfig(
    level=logging.INFO,
    format='%(name)s - %(asctime)s - %(levelname)s - %(message)s')

CONTROLLER_RATE_LIMIT = 0.2

@contextmanager
def FlowErrorHandler(controller: Controller):
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

class FlowController(Controller):
    """
    The Flow controller determines the flow of jobs in and out of the cluster.
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
            f'[{self.name} - Flow Controller]')
        self.logger.setLevel(logging.INFO)

    def post_init_hook(self):
        # Python thread safe queue for Informers to append events to.
        self.job_informer = Informer(JobAPI(namespace=None))

        def update_callback_fn(event):
            event_object = event.object
            # Filter for jobs that are scheduled by the Scheduler Controller and
            # are assigned to this cluster.
            if self.name in event_object.status.scheduled_clusters and event_object.get_status() == JobStatusEnum.SCHEDULED and self.name not in event_object.status.replica_status:
                self.worker_queue.put(event)

        def delete_callback_fn(event):
            event_object = event.object
            if self.name in event_object.status.scheduled_clusters:
                self.worker_queue.put(event)

        # Filtered add events and delete events are added to the worker queue.
        self.job_informer.add_event_callbacks(
            update_event_callback=update_callback_fn,
            delete_event_callback=delete_callback_fn)
        self.job_informer.start()

        #Define filter policy
        self.policy_informer = Informer(FilterPolicyAPI(namespace=None))

        def add_policy_callback_fn(event):
            self.worker_queue.put(event)
        
        def update_policy_callback_fn(event):
            self.worker_queue.put(event)

        self.policy_informer.add_event_callbacks(
            add_event_callback=add_policy_callback_fn,
            update_event_callback=update_policy_callback_fn)
        self.policy_informer.start()

    def run(self):
        self.logger.info(
            'Running flow controller - Manages job submission and eviction from the cluster.'
        )
        while True:
            with FlowErrorHandler(self):
                self.controller_loop()
            time.sleep(CONTROLLER_RATE_LIMIT)

    def controller_loop(self):
        # Poll for jobs and execute/kill them depending on the job status.
            # Blocks until there is at least 1 element in the queue.
        event = self.worker_queue.get()
        event_key = event.event_type
        event_object = event.object
        
        cached_jobs = deepcopy(self.job_informer.get_cache())

        if isinstance(event_object, Job):
            # Handler for Job Events
            job_object = event_object
            if event_key == WatchEventEnum.UPDATE:
                self.logger.info(
                    f'Submitting job \'{job_object.get_name()}\' to cluster \'{self.name}\'.'
                )

                job_object.status.replica_status[self.name] = {JobStatusEnum.PENDING.value: job_object.spec.replicas}
                job_name = job_object.get_name()
                if self.name not in job_object.status.job_ids:
                    # To ensure no collision with prior jobs on the cluster.
                    job_object.status.job_ids[self.name] = job_name + '-' + uuid.uuid4().hex[:5]
                JobAPI(namespace=job_object.get_namespace()).update(config=job_object.model_dump(mode='json'))
                try:
                    self._submit_job(job_object)
                    self.logger.info(
                    f'Successfully submitted job \'{job_object.get_name()}\' to cluster \'{self.name}\'.'
                    )
                except:
                    self.logger.error(traceback.format_exc())
                    self.logger.error(
                        f'Failed to submit job  \'{job_object.get_name()}\' to the cluster  \'{self.name}\'. Marking job as failed.'
                    )
                    job_object.status.replica_status[self.name] = {JobStatusEnum.FAILED.value: job_object.spec.replicas}
                    JobAPI(namespace=job_object.get_namespace()).update(config=job_object.model_dump(mode='json'))
            elif event_key == WatchEventEnum.DELETE:
                # Delete Event (object is gone from Informer cache).
                if job_object.get_name() not in cached_jobs:
                    # If the job is not in the cache, it has already been deleted.
                    self._delete_job(job_object)
            else:
                self.logger.error(
                    f'Invalid event type `{event_key}` for job {job_object.get_name()}.')
        elif isinstance(event_object, FilterPolicy):
            # Handle when FilterPolicy changes.
            assert event_key in [WatchEventEnum.ADD, WatchEventEnum.UPDATE]
            filter_object = event_object
            filter_labels = filter_object.spec.labels_selector
            include = event_object.spec.cluster_filter.include
            exclude = event_object.spec.cluster_filter.exclude
            allowed_clusters = [f for f in include if f not in exclude]
            for c_job in cached_jobs.values():
                # Filter for jobs that are assigned to this cluster and match the filter labels.
                if self.name not in c_job.status.scheduled_clusters:
                    continue
                if not match_labels(c_job.metadata.labels, filter_labels):
                    continue
                if self.name not in allowed_clusters:
                    # Evict the job from the cluster (also delete it from the cluster).
                    self._delete_job(c_job)
                    c_job.status.replica_status[self.name] = {JobStatusEnum.EVICTED.value: job_object.spec.replicas}
                    JobAPI(namespace=c_job.get_namespace()).update(config=c_job.model_dump(mode='json'))
    
    def _submit_job(self, job: Job):
        self.manager_api.submit_job(job, job_name= job.status.job_ids[self.name])
        
    
    def _delete_job(self, job: Job):
        job_status =  job.status
        del job_status.scheduled_clusters[self.name]
        del job_status.replica_status[self.name]
        manager_job_name = job_status.job_ids[self.name]
        del job_status.job_ids[self.name]
        self.manager_api.delete_job(job, job_name=manager_job_name)

    def _update_job(self, job: Job):
        pass

if __name__ == '__main__':
    cluster_api = ClusterAPI()
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
    jc = FlowController('mluo-onprem')
    jc.start()