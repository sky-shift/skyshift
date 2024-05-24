"""
Job controllers track the state of running jobs on clusters.
"""

import signal
import time
import traceback
from contextlib import contextmanager
from copy import deepcopy

import requests

from skyflow import utils
from skyflow.api_client import ClusterAPI, JobAPI
from skyflow.api_client.object_api import APIException
from skyflow.cluster_manager.manager_utils import setup_cluster_manager
from skyflow.controllers import Controller
from skyflow.controllers.controller_utils import create_controller_logger
from skyflow.globals import cluster_dir
from skyflow.structs import Informer
from skyflow.templates.job_template import Job, TaskStatusEnum

DEFAULT_HEARTBEAT_TIME = 3  # seconds
DEFAULT_RETRY_LIMIT = 5


@contextmanager
def heartbeat_error_handler(controller: "JobController"):
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
        controller.logger.error("Retry limit exceeded.")
        controller.cleanup_jobs()


class JobController(Controller):  # pylint: disable=too-many-instance-attributes
    """
    Updates the status of the jobs sent by Skyflow.
    """

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

        self.logger = create_controller_logger(
            title=
            f"[{utils.unsanitize_cluster_name(self.name)} - Job Controller]",
            log_path=f'{cluster_dir(self.name)}/logs/job_controller.log')

        self.informer = Informer(JobAPI(namespace=''), logger=self.logger)
        self.retry_counter = 0
        self.cluster_obj = ClusterAPI().get(name)
        self.manager_api = setup_cluster_manager(self.cluster_obj)
        # Fetch cluster state template (cached cluster state).
        self.job_status = self.manager_api.get_jobs_status()

        # Register the cleanup function
        signal.signal(signal.SIGTERM, self.cleanup_jobs)

    def post_init_hook(self):
        # Keeps track of cached job state.
        self.informer.start()

    def run(self):
        self.logger.info(
            "Running job controller - Updates the status of the jobs sent by Skyflow."
        )
        while True:
            start = time.time()
            with heartbeat_error_handler(self):
                self.controller_loop()
            end = time.time()
            if end - start < self.heartbeat_interval:
                time.sleep(self.heartbeat_interval - (end - start))

    def controller_loop(self):
        self.job_status = self.manager_api.get_jobs_status()
        # Copy Informer cache to get the jobs stored in API server.
        informer_object = deepcopy(self.informer.get_cache())
        prev_jobs = list(informer_object.keys())
        # Filter jobs that have a replica status entry for the specified cluster
        filtered_jobs = [
            job_id for job_id in prev_jobs
            if self.name in informer_object[job_id].status.replica_status
        ]
        for job_name, tasks in self.job_status["tasks"].items():
            # For jobs that have been submitted to the cluster but do not appear on Sky Manager.
            try:
                filtered_jobs.remove(job_name)
            except ValueError:
                continue

            cached_job = informer_object[job_name]
            new_task_status = {}
            for _, state in tasks.items():
                # Update the count for each state
                if state in new_task_status:
                    new_task_status[state] += 1
                else:
                    new_task_status[state] = 1
            self.update_job(cached_job, new_task_status, tasks,
                            self.job_status["containers"])

        # For jobs that are no longer present on the cluster due to expiration or deletion.
        for job_name in filtered_jobs:
            self.logger.warning("Job %s not found on cluster.", job_name)
            cached_job = informer_object[job_name]
            # Ensure the job was in the RUNNING state before marking it as FAILED
            if TaskStatusEnum.RUNNING.value in cached_job.status.replica_status.get(
                    self.name, {}).values():
                self.update_job(
                    cached_job, {
                        TaskStatusEnum.FAILED.value:
                        sum(cached_job.status.replica_status[
                            self.name].values())
                    }, {}, self.job_status["containers"])

    def update_job(self, job: Job, status: dict, tasks: dict,
                   containers: dict):
        """
        Update the status of the job on the API server.
        Args:
            job (Job): Job object that needs to be updated.
            status (dict): Status of the job.
            tasks (dict): Task status of the job.
            containers (dict): Containers status of the job.
        """
        try:
            job.status.replica_status[self.name] = status
            job.status.task_status[self.cluster_obj.metadata.name] = tasks
            job.status.container_status = containers
            JobAPI(namespace=job.get_namespace()).update(config=job.model_dump(
                mode="json"))
        except APIException:
            job = JobAPI(namespace=job.get_namespace()).get(
                name=job.get_name())
            job.status.replica_status[self.name] = status
            JobAPI(namespace=job.get_namespace()).update(config=job.model_dump(
                mode="json"))

    def cleanup_jobs(self, _sig=None, _frame=None):
        """Mark all jobs as EVICTED when the process is terminating."""
        informer_object = deepcopy(self.informer.get_cache())
        prev_jobs = list(informer_object.keys())
        self.logger.info("Jobs: %s", prev_jobs)
        # Filter jobs that have a replica status entry for the specified cluster
        filtered_jobs = [
            job_id for job_id in prev_jobs
            if self.name in informer_object[job_id].status.replica_status
        ]
        self.logger.warning("Evicting jobs from cluster: %s.", self.name)
        self.logger.info("Jobs to evict: %s.", filtered_jobs)
        # Mark all jobs as evicted.
        for job_name in filtered_jobs:
            job = informer_object[job_name]
            job.status.replica_status[self.name] = {
                TaskStatusEnum.EVICTED.value:
                sum(job.status.replica_status[self.name].values())
            }
            JobAPI(namespace=job.get_namespace()).update(config=job.model_dump(
                mode="json"))


# Testing purposes.
# if __name__ == "__main__":
#     cluster_api = ClusterAPI()
#     try:
#         cluster_api.create({
#             "kind": "Cluster",
#             "metadata": {
#                 "name": "mluo-onprem"
#             },
#             "spec": {
#                 "manager": "k8",
#             },
#         })
#     except:
#         pass
#     jc = JobController("mluo-onprem")
#     jc.start()
