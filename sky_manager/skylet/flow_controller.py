from contextlib import contextmanager
from copy import deepcopy
from queue import Queue
import logging
import requests
import traceback
import time

from sky_manager.structs import Informer
from sky_manager.controllers import Controller
from sky_manager.utils.utils import setup_cluster_manager
from sky_manager.templates.job_template import Job, JobStatusEnum
from sky_manager.templates.cluster_template import Cluster
from sky_manager.api_client import *

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
        cluster_dict = ClusterAPI().get(name)
        cluster_obj = Cluster.from_dict(cluster_dict)
        self.manager_api = setup_cluster_manager(cluster_obj)

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        self.logger = logging.getLogger(
            f'[{self.name} - Flow Controller]')
        self.logger.setLevel(logging.INFO)

        self.worker_queue = Queue()

        # self.policy_informer = Informer('filterpolicies')

        # def add_policy_callback_fn(event):
        #     self.worker_queue.put(event)

        # self.policy_informer.add_event_callbacks(
        #     add_event_callback=add_policy_callback_fn,
        #     delete_event_callback=None)
        # self.policy_informer.start()

    def post_init_hook(self):
        # Python thread safe queue for Informers to append events to.
        self.job_informer = Informer(JobAPI(namespace=None))

        def update_callback_fn(event):
            event_object = event.object
            # Filter for jobs that are scheduled by the Scheduler Controller and
            # are assigned to this cluster.
            if event_object.status.cluster == self.name and event_object.get_status() == JobStatusEnum.SCHEDULED:
                self.worker_queue.put(event)

        def delete_callback_fn(event):
            self.worker_queue.put(event)

        # Filtered add events and delete events are added to the worker queue.
        self.job_informer.add_event_callbacks(
            update_event_callback=update_callback_fn,
            delete_event_callback=delete_callback_fn)
        self.job_informer.start()

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
        job_object = event.object
        
        cached_jobs = deepcopy(self.job_informer.get_cache())
        # Handler for Job Events
        if job_object.meta.name in cached_jobs:
            self.logger.info(
                f'Submitting job \'{job_object.meta.name}\' to cluster \'{self.name}\'.'
            )
            try:
                self.manager_api.submit_job(job_object)
                job_object.status.update_status(
                    JobStatusEnum.PENDING.value)
            except:
                self.logger.error(traceback.format_exc())
                self.logger.error(
                    f'Failed to submit job  \'{job_object.meta.name}\' to the cluster  \'{self.name}\'. Marking job as failed.'
                )
                job_object.status.update_status(
                    JobStatusEnum.FAILED.value)
                job_object.meta.annotations[
                    self.name] = 'reason:job-submission-failure'
            JobAPI(namespace=job_object.meta.namespace).update(config=dict(job_object))
        else:
            # Delete Event (object is gone from Informer cache).
            self.manager_api.delete_job(job_object)


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


# Handler for changes in Policy
# if not event_object and event_object['kind'] == 'FilterPolicy':
#     fp_namespace = event_object['metadata']['namespace']
#     fp_labels = event_object['spec']['labelsSelector']
#     fp_include = event_object['spec']['clusterFilter'][
#         'include']
#     fp_exclude = event_object['spec']['clusterFilter'][
#         'exclude']
#     for job_dict in cached_jobs.values():
#         if job_dict['status']['cluster'] != self.cluster_name:
#             continue
#         job_labels = job_dict['metadata']['labels']
#         is_subset = all(k in job_labels and job_labels[k] == v
#                         for k, v in fp_labels.items())
#         if is_subset and job_dict['status']['status'] in [
#                 'PENDING', 'RUNNING'
#         ] and fp_namespace == job_dict['metadata'][
#                 'namespace'] and job_dict['status'][
#                     'cluster'] not in fp_include and job_dict[
#                         'status']['cluster'] in fp_exclude:
#             job_object = Job.from_dict(job_dict)
#             job_object.status.update_status(
#                 JobStatusEnum.INIT.value)
#             job_object.meta.annotations[
#                 self.
#                 cluster_name] = 'reason:filter-policy-change'
#             job_object.status.update_cluster(None)
#             job_api_object.Update(
#                 config=dict(job_object),
#                 namespace=job_object.meta.namespace)
#     self.worker_queue.task_done()
#     continue