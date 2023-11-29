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
        time.sleep(0.5)
        controller.retry_counter += 1
    
    if controller.retry_counter > controller.retry_limit:
        controller.logger.error(f'Retry limit exceeded. Marking pending/running jobs in ERROR state.')


class JobController(Controller):

    def __init__(self, name, heartbeat_interval: int = DEFAULT_HEARTBEAT_TIME, retry_limit: int = DEFAULT_RETRY_LIMIT):
        super().__init__()

        self.name = name
        self.heartbeat_interval = heartbeat_interval
        self.retry_limit = retry_limit


        cluster_obj = ClusterAPI().get(name)
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

            # Copy Informer cache to get the jobs stored in API server.
            informer_object = deepcopy(self.informer.get_cache())
            prev_jobs = list(informer_object.keys())
            for job_name, fetched_status in self.job_status.items():
                # For jobs that have been submitted to the cluster but do not appear on Sky Manager.
                if job_name not in prev_jobs:
                    continue
                else:
                    cached_job = informer_object[job_name]  

                self.update_job(cached_job, fetched_status)          
    
    def update_job(self, job: Job, status: dict):
        try:
            job.status.replica_status[self.name] = status
            JobAPI(namespace=job.get_namespace()).update(config=job.model_dump(mode='json'))
        except:
            job = JobAPI(namespace=job.get_namespace()).get(name=job.get_name())
            job.status.replica_status[self.name] = status
            JobAPI(namespace=job.get_namespace()).update(config=job.model_dump(mode='json'))
            

# Testing purposes.
if __name__ == '__main__':
    cluster_api = ClusterAPI()
    try:
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
    except:
        pass
    jc = JobController('mluo-onprem')
    jc.start()
