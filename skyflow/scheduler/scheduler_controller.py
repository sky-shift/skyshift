"""Scheduler controller determines which cluster (or clusters) a job should be placed on.

This controller does not schedule tasks/pods, but instead schedules at a higher level
of abstraction - jobs (groups of tasks/pods). This enables the scheduler to satisfy
gang/coscheduling, colocation, and governance requirements that are not possible with
the default Kubernetes scheduler (without CRDs or custom controllers).
"""

import logging
import os
import queue
from copy import deepcopy
from typing import Dict, List

from skyflow.api_client import ClusterAPI, JobAPI
from skyflow.controllers import Controller
from skyflow.scheduler.plugins import ClusterAffinityPlugin, DefaultPlugin
from skyflow.structs import Informer
from skyflow.templates import Cluster, Job, JobStatusEnum, TaskStatusEnum
from skyflow.templates.cluster_template import ClusterStatusEnum

logging.basicConfig(
    level=logging.INFO,
    format="%(name)s - %(asctime)s - %(levelname)s - %(message)s")


def aggregate_job_status(replica_status: Dict[str, Dict[str, int]]):
    """Merges the status of replicas across clusters."""
    merged_status = {}
    for status in replica_status.values():
        for task_status, count in status.items():
            if task_status not in merged_status:
                merged_status[task_status] = 0
            merged_status[task_status] += count
    return merged_status


class SchedulerController(Controller):
    """
    Scheduler controller determines which cluster (or spread of clusters)
    a job should be placed on.
    """

    def __init__(self) -> None:
        super().__init__()
        self.logger = logging.getLogger("[Scheduler Controller]")
        self.logger.setLevel(
            getattr(logging,
                    os.getenv('LOG_LEVEL', 'INFO').upper(), logging.INFO))

        # Assumed FIFO
        self.workload_queue: List[Job] = []

        # Thread safe queue for Informers to append events to.
        self.event_queue: queue.Queue = queue.Queue()

        # Initialize informers.
        self.cluster_informer: Informer = Informer(ClusterAPI(),
                                                   logger=self.logger)
        self.job_informer: Informer = Informer(JobAPI(namespace=''),
                                               logger=self.logger)
        self.prev_alloc_capacity: Dict[str, Dict[str, float]] = {}

        # Load scheduler plugins
        # @TODO(mluo): Make this dynamic.
        self.plugins = [DefaultPlugin(), ClusterAffinityPlugin()]

    def post_init_hook(self):

        def add_job_callback_fn(event):
            event_object = event.object
            event_status = event_object.status
            # Filter for newly created jobs (jobs without replica status field).
            if not event_status.replica_status:
                self.event_queue.put(event)

        def update_job_callback_fn(_, event):
            event_object = event.object
            replica_status = event_object.status.replica_status
            # Filter for evicted tasks in a job.
            if TaskStatusEnum.EVICTED.value in aggregate_job_status(
                    replica_status):
                self.event_queue.put(event)

        self.job_informer.add_event_callbacks(
            add_event_callback=add_job_callback_fn,
            update_event_callback=update_job_callback_fn,
        )
        self.job_informer.start()

        def add_cluster_callback_fn(event):
            # Only add event when allocatable cluster resources have changed.
            event_object = event.object
            cluster_name = event_object.get_name()
            cluster_alloc = event_object.status.allocatable_capacity
            if cluster_alloc != self.prev_alloc_capacity.get(
                    cluster_name, None):
                self.event_queue.put(event)
                self.prev_alloc_capacity[cluster_name] = cluster_alloc

        self.cluster_informer.add_event_callbacks(
            add_event_callback=add_cluster_callback_fn)
        self.cluster_informer.start()

    def run(self):
        self.logger.info(
            "Running Scheduler controller - Manages workload submission over multiple clusters."
        )
        super().run()

    def apply_filter_plugins(self, job: Job,
                             clusters: List[Cluster]) -> List[Cluster]:
        """Applies filter plugins to filter out unschedulable clusters."""
        filtered_clusters = []
        for cluster in clusters:
            remove_cluster = False
            for plugin in self.plugins:
                status = plugin.filter(cluster, job)
                if status.is_unschedulable():
                    remove_cluster = True
                    break
            if not remove_cluster:
                filtered_clusters.append(cluster)
        return filtered_clusters

    def apply_score_plugins(self, job: Job, clusters: List[Cluster]):
        """Applies score plugins to rank clusters based on a cumulative scoring function."""
        score_tuples = []
        for cluster in clusters:
            total_score: float = 0
            for plugin in self.plugins:
                score, status = plugin.score(cluster, job)
                if status.is_successful():
                    total_score += score
                elif status.is_unschedulable():
                    total_score = 0
                    break
            score_tuples.append((cluster, total_score))
        # Sort tuple by score and get the list of clusters
        return [
            x[0]
            for x in sorted(score_tuples, key=lambda x: x[1], reverse=True)
        ]

    def apply_spread_plugins(self, job: Job, clusters: List[Cluster]):
        """Applies spread plugins to spread the job across clusters."""
        # Can only use one spread plugin at a time.
        spread_plugin = self.plugins[0]
        cluster_spread, status = spread_plugin.spread(clusters, job)
        if status.is_successful():
            return cluster_spread
        return None

    def controller_loop(self):
        # Blocks until there is at least 1 element in the queue or until timeout.
        event = self.event_queue.get()
        event_object = event.object

        # Only add jobs that have newly arrived or failed over from a prior cluster.
        if isinstance(event_object, Job):
            self.workload_queue.append(event_object)

        if len(self.workload_queue) == 0:
            return

        # Main Scheduling loop.
        cached_clusters = deepcopy(self.cluster_informer.get_cache())
        # Convert to list of clusters
        self.logger.debug("Cached clusters: %s", cached_clusters)
        clusters = [
            cluster for cluster in cached_clusters.values()
            if cluster.status.status != ClusterStatusEnum.ERROR.value
        ]
        self.logger.debug("Clusters: (list) %s", clusters)
        idx_list = []
        for job_idx, job in enumerate(self.workload_queue):
            # Filter for valid clusters based on filter plugins.
            filtered_clusters = self.apply_filter_plugins(job, clusters)
            # Rank clusters with a scoring function.
            ranked_clusters = self.apply_score_plugins(job, filtered_clusters)
            # Compute spread. Defaults to the spread plugin in DefaultPlugin.
            spread_replicas = self.apply_spread_plugins(job, ranked_clusters)
            self.logger.debug("Spread replicas: %s", spread_replicas)
            self.logger.debug("Job status: %s", job.status.replica_status)
            self.logger.debug("Ranked clusters: %s", ranked_clusters)
            self.logger.debug("Filtered clusters: %s", filtered_clusters)
            if spread_replicas:
                job.status.update_replica_status({
                    c_name: {
                        TaskStatusEnum.INIT.value: replicas
                    }
                    for c_name, replicas in spread_replicas.items()
                })
                job.status.update_status(JobStatusEnum.ACTIVE.value)
                idx_list.append(job_idx)
                self.logger.info("Sending job %s to clusters %s.",
                                 job.get_name(), spread_replicas)
            else:
                self.logger.info(
                    "Unable to schedule job %s. Marking it as failed.",
                    job.get_name())
                idx_list.append(job_idx)
                job.status.update_status(JobStatusEnum.FAILED.value)
            JobAPI(namespace=job.get_namespace()).update(config=job.model_dump(
                mode="json"))
            break

        for job_idx in reversed(idx_list):
            del self.workload_queue[job_idx]


# Testing Scheduler Controller.
if __name__ == "__main__":
    controller = SchedulerController()
    controller.start()
