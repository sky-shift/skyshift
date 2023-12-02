"""Scheduler controller determines which cluster (or clusters) a job should be placed on.

This controller does not schedule tasks/pods, but instead schedules at a higher level of abstraction - jobs (groups of tasks/pods). This enables the scheduler to satisfy gang/coscheduling, colocation, and governance requirements that are not possible with the default Kubernetes scheduler (without CRDs or custom controllers).
"""
from contextlib import contextmanager
from collections import OrderedDict
from copy import deepcopy
import logging
import queue
import requests
import traceback
from typing import Dict

from sky_manager.controllers import Controller
from sky_manager.structs import Informer
from sky_manager.api_client import *
from sky_manager.templates import Job, JobStatusEnum, ResourceEnum, TaskStatusEnum

logging.basicConfig(
    level=logging.INFO,
    format='%(name)s - %(asctime)s - %(levelname)s - %(message)s')

def aggregate_job_status(replica_status: Dict[str, Dict[str, int]]):
    """Merges the status of replicas across clusters."""
    merged_status = {}
    for status in replica_status.values():
        for task_status, count in status.items():
            if task_status not in merged_status:
                merged_status[task_status] = 0
            merged_status[task_status] += count
    return merged_status


@contextmanager
def SchedulerErrorHandler(controller: Controller):
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


class SchedulerController(Controller):

    def __init__(self) -> None:
        super().__init__()
        self.logger = logging.getLogger('[Scheduler Controller]')
        self.logger.setLevel(logging.INFO)

        # Assumed FIFO
        self.workload_queue = []

        #Thread safe queue for Informers to append events to.
        self.event_queue = queue.Queue()

    def post_init_hook(self):
        def add_job_callback_fn(event):
            event_object = event.object
            event_status = event_object.status
            # Filter for newly created jobs (jobs without replica status field).
            if not event_status.replica_status:
                self.event_queue.put(event)
        
        def update_job_callback_fn(event):
            event_object = event.object
            replica_status = event_object.status.replica_status
            # Filter for evicted tasks in a job.
            if TaskStatusEnum.EVICTED.value in aggregate_job_status(replica_status):
                self.event_queue.put(event)

        self.job_informer = Informer(JobAPI(namespace=None))
        self.job_informer.add_event_callbacks(
            add_event_callback=add_job_callback_fn, update_event_callback=update_job_callback_fn)
        self.job_informer.start()

        self.prev_alloc_capacity = {}
        def add_cluster_callback_fn(event):
            # Only add event when allocatable cluster resources have changed.
            event_object = event.object
            cluster_name = event_object.get_name()
            cluster_alloc = event_object.status.allocatable_capacity
            if cluster_alloc != self.prev_alloc_capacity.get(cluster_name, None):
                self.event_queue.put(event)
                self.prev_alloc_capacity[cluster_name] = cluster_alloc

        self.cluster_informer = Informer(ClusterAPI())
        self.cluster_informer.add_event_callbacks(
            add_event_callback=add_cluster_callback_fn)
        self.cluster_informer.start()

    def run(self):
        self.logger.info(
            'Running Scheduler controller - Manages workload submission over multiple clusters.'
        )
        while True:
            with SchedulerErrorHandler(self):
                self.controller_loop()
    

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
        clusters = OrderedDict(deepcopy(self.cluster_informer.get_cache()))
        idx_list = []
        for job_idx, job in enumerate(self.workload_queue):
            # Filter for valid clusters based on filter policies.
            filtered_clusters = self.filter_clusters(job, clusters)
            # Rank clusters by their approximate availability.
            ranked_clusters = self.rank_clusters(job, filtered_clusters)
            # Compute replica spread across clusters. Default policy is best-fit bin-packing.
            # Place as many replicas on the fullest clusters.
            spread_replicas = self.compute_replicas_spread(job, ranked_clusters)
            if spread_replicas:
                job.status.update_replica_status({c_name : {TaskStatusEnum.INIT.value: replicas} for c_name, replicas in spread_replicas.items()})
                job.status.update_status(JobStatusEnum.ACTIVE.value)
                idx_list.append(job_idx)
                self.logger.info(
                    f'Sending job {job.get_name()} to clusters {spread_replicas}.'
                )
            else:
                self.logger.info(
                    f'Unable to schedule job {job.get_name()}. Marking it as failed.'
                )
                idx_list.append(job_idx)
                job.status.update_status(JobStatusEnum.FAILED.value)
            JobAPI(namespace=job.get_namespace()).update(config=job.model_dump(mode='json'))
            break

        for job_idx in reversed(idx_list):
            del self.workload_queue[job_idx]
    
    def compute_replicas_spread(self, job, ranked_clusters):
        job_replicas = job.spec.replicas
        job_clusters = {}
        job_resource = deepcopy(job.spec.resources)
        
        ranked_clusters = list(ranked_clusters.items())
        # Greedily assign clusters replicas.
        total_cluster_replicas = 0

        def is_subset_and_values_smaller(dict1, dict2):
            # Check if all keys in dict2 are in dict1
            if all(key in dict1 for key in dict2):
                # Check if all values in dict2 are smaller than corresponding values in dict1
                return all(dict2[key] <= dict1[key] for key in dict2)
            else:
                return False
        for cluster_name, cluster_obj in ranked_clusters:
            cluster_replicas = 0
            alloc_capacity = deepcopy(cluster_obj.status.allocatable_capacity)
            # Predict how many replicas can fit onto each node for each cluster.
            for _, node_resource in alloc_capacity.items():
                while True:
                    if total_cluster_replicas == job_replicas:
                        break
                    if is_subset_and_values_smaller(node_resource, job_resource):
                        for resource_type, resource_count in node_resource.items():
                            if resource_type in job_resource:
                                node_resource[resource_type] -= job_resource[resource_type]
                        total_cluster_replicas+=1
                        cluster_replicas+=1
                    else:
                        break
            job_clusters[cluster_name] = cluster_replicas
            if total_cluster_replicas == job_replicas:
                break
        # Can't schedule job. Returns a null dict.
        if total_cluster_replicas < job_replicas:
            return {}
        
        return {k:v for k,v in job_clusters.items() if v>0}


    def filter_clusters(self, job, clusters: dict):
        # Filter for clusters.
        filter_policy_api = FilterPolicyAPI(namespace=job.get_namespace())
        all_policies = filter_policy_api.list()

        # Find filter policies that have labels that are a subset of the job's labels.
        filter_policies = []
        for fp in all_policies.objects:
            fp_dict_labels = fp.spec.labels_selector
            job_labels = job.metadata.labels
            is_subset = False
            if fp_dict_labels:
                is_subset = all(k in job_labels and job_labels[k] == v
                                for k, v in fp_dict_labels.items())
            if is_subset:
                filter_policies.append(fp)

        # Filter for clusters that satisfy the filter policies.
        for fp in filter_policies:
            include_list = fp.spec.cluster_filter.include
            exclude_list = fp.spec.cluster_filter.exclude
            cluster_keys = list(clusters.keys())
            for c_name in cluster_keys:
                if c_name not in include_list:
                    del clusters[c_name]

            for c_name in exclude_list:
                if c_name in clusters:
                    del clusters[c_name]
        return clusters

    def rank_clusters(self, job: Job, clusters: dict):
        # Rank cluster by their availability (i.e. load-balancing).
        # Whatever scores highest on the **dot product** of the cluster's resources and the job's resources. (such as in the Tetris paper, Robert Grandl)
        sum_clusters = []
        for cluster in clusters.items():
            cluster_name, cluster_obj = cluster
            resources = cluster_obj.status.allocatable_capacity
            sum_resources = {}
            for _, node_resources in resources.items():
                for resource_type, resource_count in node_resources.items():
                    if resource_type not in sum_resources:
                        sum_resources[resource_type] = 0
                    sum_resources[resource_type] += resource_count
            sum_clusters.append((cluster_name, sum_resources))
        
        def sorting_func(cluster_tuple):
            _, cluster_resources = cluster_tuple
            score = 0
            job_resources = job.spec.resources
            for resource_type, resource_count in job_resources.items():
                # Normalize score.
                if resource_count ==0:
                    continue
                score += cluster_resources.get(resource_type, 0)/resource_count
            return score

        sum_clusters = sorted(sum_clusters,
                          key=sorting_func,
                          reverse=True)
        index_map = {value[0]: index for index, value in enumerate(sum_clusters)}
        sorted_clusters = sorted(list(clusters.items()), key=lambda x:  index_map[x[0]])
        return OrderedDict(sorted_clusters)


# Testing Scheduler Controller.
if __name__ == '__main__':
    controller = SchedulerController()
    controller.start()
