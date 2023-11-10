"""
Source code for the log controllers that keep track of the state of the cluster and jobs. These controllers are launched in Skylet.
"""
from contextlib import contextmanager
from copy import deepcopy
import logging
import requests
import time

import traceback

from sky_manager.controllers import Controller
from sky_manager.templates.job_template import Job, JobStatusEnum
from sky_manager.templates.cluster_template import Cluster
from sky_manager.utils.utils import setup_cluster_manager
from sky_manager.structs import Informer
from sky_manager.api_client import *

logging.basicConfig(
    level=logging.INFO,
    format='%(name)s - %(asctime)s - %(levelname)s - %(message)s')

DEFAULT_HEARTBEAT_TIME = 3
DEFAULT_RETRY_LIMIT = 3

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
        controller.logger.error('Encountered unusual error. Trying again.')
        controller.retry_counter += 1
    
    if controller.retry_counter > controller.retry_limit:
        controller.logger.error(f'Retry limit exceeded. Marking pending/running jobs in ERROR state.')
        controller.update_unhealthy_cluster()


class JobController(Controller):

    def __init__(self, name, heartbeat_interval: int = DEFAULT_HEARTBEAT_TIME, retry_limit: int = DEFAULT_RETRY_LIMIT):
        super().__init__()

        self.name = name
        self.heartbeat_interval = heartbeat_interval
        self.retry_limit = retry_limit


        cluster_dict = ClusterAPI().get(name)
        cluster_obj = Cluster.from_dict(cluster_dict)
        self.manager_api = setup_cluster_manager(cluster_obj)
        # Fetch cluster state template (cached cluster state).
        self.job_status = self.manager_api.get_jobs_status()

        self.logger = logging.getLogger(
            f'[{self.name} - Job Controller]')
        self.logger.setLevel(logging.INFO)
    
    def post_init_hook(self):
        # Keeps track of cached job state.
        self.informer = Informer(JobAPI(namespace=None))
        self.informer.start()

    def run(self):
        self.logger.info(
            'Running job controller - Updates the status of the jobs sent by Sky Manager.'
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
            self.job_status = self.manager_api.get_jobs_status()
            # Copy Informer to get the current job statuses.
            informer_object = deepcopy(self.informer.get_cache())
            prev_status = {
                k: v.get_status()
                for k, v in informer_object.items()
            }
            for job_name, new_job_status in self.job_status.items():
                # For jobs that have been submitted to the cluster but do not appear on Sky Manager.
                if job_name not in prev_status:
                    # temp_job = Job(meta={
                    #     'name': job_name,
                    # })
                    # temp_job.status.update_status(new_job_status.curStatus)
                    # temp_job.status.update_clusters(self.name)
                    continue
                # Save API calls.
                if new_job_status.curStatus == JobStatusEnum.COMPLETED.value and prev_status[
                        job_name] == new_job_status.curStatus:
                    continue

                temp_job = informer_object[job_name]
                temp_job.status.update_status(new_job_status.curStatus)
                try:
                    JobAPI(namespace=temp_job.meta.namespace).update(config=dict(temp_job))
                except Exception as e:
                    JobAPI(namespace=temp_job.meta.namespace).create(config=dict(temp_job))

# Testing purposes.
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
    jc = JobController('mluo-onprem')
    jc.start()
