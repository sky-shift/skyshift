"""
Flow Controller - Submits and removes jobs from the cluster.
"""
import traceback
from contextlib import contextmanager
from copy import deepcopy
from queue import Queue

import requests

from skyshift import utils
from skyshift.api_client import FilterPolicyAPI, JobAPI
from skyshift.cluster_manager.manager_utils import setup_cluster_manager
from skyshift.controllers import Controller
from skyshift.controllers.controller_utils import create_controller_logger
from skyshift.globals import cluster_dir
from skyshift.structs import Informer
from skyshift.templates import (FilterPolicy, Job, TaskStatusEnum,
                                WatchEventEnum)
from skyshift.templates.cluster_template import Cluster
from skyshift.utils import match_labels


@contextmanager
def flow_error_handler(controller: Controller):
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


class FlowController(Controller):
    """
    The Flow controller determines the flow of jobs in and out of the cluster.
    """

    def __init__(self, cluster: Cluster) -> None:
        super().__init__(cluster)
        self.name = cluster.get_name()
        self.cluster_obj = cluster
        self.manager_api = setup_cluster_manager(self.cluster_obj)
        self.worker_queue: Queue = Queue()

        self.logger = create_controller_logger(
            title=
            f"[{utils.unsanitize_cluster_name(self.name)} - Flow Controller]",
            log_path=f'{cluster_dir(self.name)}/logs/flow_controller.log')

        self.job_informer = Informer(JobAPI(namespace=''), logger=self.logger)
        self.policy_informer = Informer(FilterPolicyAPI(namespace=''),
                                        logger=self.logger)

    def post_init_hook(self):

        def update_callback_fn(_, event):
            event_object = event.object
            # Filter for jobs that are scheduled by the Scheduler Controller and
            # are assigned to this cluster.
            if self.name in event_object.status.replica_status:
                if self.name not in event_object.status.job_ids:
                    self.worker_queue.put(event)

        def delete_callback_fn(event):
            event_object = event.object
            if self.name in event_object.status.replica_status:
                self.worker_queue.put(event)

        # Filtered add events and delete events are added to the worker queue.
        self.job_informer.add_event_callbacks(
            update_event_callback=update_callback_fn,
            delete_event_callback=delete_callback_fn,
        )
        self.job_informer.start()

        def add_policy_callback_fn(event):
            self.worker_queue.put(event)

        def update_policy_callback_fn(event):
            self.worker_queue.put(event)

        self.policy_informer.add_event_callbacks(
            add_event_callback=add_policy_callback_fn,
            update_event_callback=update_policy_callback_fn,
        )
        self.policy_informer.start()

    def run(self):
        self.logger.info(
            "Running flow controller - Manages job submission and eviction from the cluster."
        )
        while True:
            with flow_error_handler(self):
                self.controller_loop()

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
                job_name = job_object.get_name()
                try:
                    self._submit_job(job_object)
                    self.logger.info(
                        "Successfully submitted job '%s' to cluster '%s'.",
                        job_name, self.name)
                except Exception:  # pylint: disable=broad-except
                    self.logger.error(traceback.format_exc())
                    self.logger.error(
                        "Failed to submit job  '%s' to the cluster '%s'. "
                        "Marking job as failed.", job_name, self.name)
                    job_object.status.replica_status[self.name] = {
                        TaskStatusEnum.FAILED.value:
                        sum(job_object.status.replica_status[
                            self.name].values())
                    }
                JobAPI(namespace=job_object.get_namespace()).update(
                    config=job_object.model_dump(mode="json"))
            elif event_key == WatchEventEnum.DELETE:
                # If the job is not in the cache, it has already been deleted.
                self._delete_job(job_object)
            else:
                self.logger.error("Invalid event type `%s` for job %s.",
                                  event_key, job_object.get_name())
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
                    c_job.status.replica_status[self.name] = {
                        TaskStatusEnum.EVICTED.value:
                        sum(job_object.status.replica_status[
                            self.name].values())
                    }
                    JobAPI(namespace=c_job.get_namespace()).update(
                        config=c_job.model_dump(mode="json"))

    def _submit_job(self, job: Job):
        manager_response = self.manager_api.submit_job(job)
        job.status.job_ids[self.name] = manager_response["manager_job_id"]

    def _delete_job(self, job: Job):
        job_status = job.status
        self.manager_api.delete_job(job)
        del job_status.replica_status[self.name]
        del job_status.job_ids[self.name]
