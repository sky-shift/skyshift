"""Scheduler controller determines which cluster (or clusters) a job should be placed on.

Unlike Kubernetes scheduler, this controller schedules batch jobs and deployments/services over clusters. This enables the scheduler to satisfy gang/coscheduling, colocation, and governance requiremnts.
"""
from collections import OrderedDict
from copy import deepcopy
import logging
import queue
import time
import traceback

from sky_manager.controllers import Controller
from sky_manager.utils import Informer
from sky_manager.api_client import *
from sky_manager.templates.job_template import Job


class SchedulerController(Controller):

    def __init__(self) -> None:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(f'Scheduler Controller')
        self.logger.setLevel(logging.INFO)

        #Thread safe queue for Informers to append events to.
        self.event_queue = queue.Queue()
        # Assumed FIFO
        self.job_queue = []
        self.job_api = JobAPI()
        super().__init__()

    def post_init_hook(self):

        def add_job_callback_fn(event):
            event_object = event[1]
            # Filter for jobs that are scheduled by the Scheduler Controller and
            # are assigned to this cluster.
            if event_object['status']['status'] == 'INIT':
                self.event_queue.put(event)

        # Filtered Add events and Delete events are added to the worker queue.
        self.job_informer = Informer('jobs')
        self.job_informer.add_event_callbacks(
            add_event_callback=add_job_callback_fn, delete_event_callback=None)
        self.job_informer.start()

        self.prev_alloc_capacity = {}

        def add_cluster_callback_fn(event):
            # Only add event when allocatable cluster resources have changed.
            event_key = event[0]
            event_object = event[1]
            if event_object['status'][
                    'allocatable'] != self.prev_alloc_capacity.get(
                        event_key, None):
                self.event_queue.put(event)
            self.prev_alloc_capacity[event_key] = event_object['status'][
                'allocatable']

        self.cluster_informer = Informer('clusters')
        self.cluster_informer.add_event_callbacks(
            add_event_callback=add_cluster_callback_fn,
            delete_event_callback=None)
        self.cluster_informer.start()

    def run(self):
        self.logger.info(
            'Running Scheduler controller - Manages job submission over multiple clusters.'
        )
        while True:
            # Blocks until there is at least 1 element in the queue or until timeout.
            event = self.event_queue.get()
            try:
                event_object = event[1]

                # Only add jobs that have new arrived or failed over from a prior cluster.
                if event_object['kind'] == 'Job' and event_object['status'][
                        'status'] == 'INIT':
                    self.job_queue.append(event_object)
                else:
                    self.event_queue.task_done()
                    continue
                if len(self.job_queue) == 0:
                    self.event_queue.task_done()
                    continue

                # Main Scheduling loop.
                # Local cache of clusters for this scheduling loop.
                clusters = deepcopy(self.cluster_informer.get_cache())
                clusters = dict(clusters.items())
                sched_jobs = []
                idx_list = []
                for job_idx, job in enumerate(self.job_queue):
                    filtered_clusters = self.filter_clusters(job, clusters)
                    ranked_clusters = self.rank_clusters(
                        job, filtered_clusters)
                    if clusters:
                        # Fetch the top scoring cluster.
                        top_cluster = ranked_clusters[0][0]
                        job_obj = Job.from_dict(job)
                        job_obj.status.update_cluster(top_cluster)
                        job_obj.status.update_status('SCHEDULED')
                        job_obj_dict = dict(job_obj)
                        self.job_api.Update(config=job_obj_dict,
                                            namespace=job_obj.meta.namespace)
                        sched_jobs.append(job_obj_dict)
                        idx_list.append(job_idx)
                        self.logger.info(
                            f'Sending job {job_obj.meta.name} to cluster {top_cluster}.'
                        )
                    else:
                        self.logger.info(
                            f'Unable to schedule job {job_obj.meta.name}. Marking it as failed.'
                        )
                    break

                for job_idx in reversed(idx_list):
                    del self.job_queue[job_idx]
            except:
                print(traceback.format_exc())
                time.sleep(1)
            self.worker_queue.task_done()

    def filter_clusters(self, job, clusters: dict):
        # Filter for clusters.
        filter_policy_api = FilterPolicyAPI()
        all_policies = filter_policy_api.List()

        # Find filter policies that have labels that are a subset of the job's labels.
        filter_policies = []
        for fp_dict in all_policies['items']:
            fp_dict_labels = fp_dict['spec']['labelsSelector']
            job_labels = job['metadata']['labels']
            if fp_dict_labels:
                is_subset = all(k in job_labels and job_labels[k] == v
                                for k, v in fp_dict_labels.items())
            else:
                is_subset = False

            if is_subset:
                filter_policies.append(fp_dict)

        # Filter for clusters that satisfy the filter policies.
        for fp_dict in filter_policies:
            include_list = fp_dict['spec']['clusterFilter']['include']
            exclude_list = fp_dict['spec']['clusterFilter']['exclude']
            cluster_keys = list(clusters.keys())
            for c_name in cluster_keys:
                if c_name not in include_list:
                    del clusters[c_name]

            for c_name in exclude_list:
                if c_name in clusters:
                    del clusters[c_name]
        return clusters

    def rank_clusters(self, job, clusters: dict):
        # For now this policy is rank cluster by their availability". (load-balancing)
        sum_clusters = []
        for cluster in clusters.items():
            cluster_name, cluster_dict = cluster
            resources = cluster_dict['status']['allocatable']
            sum_resources = {'cpu': 0, 'memory': 0, 'gpu': 0}
            if resources:
                for _, node_resources in resources.items():
                    sum_resources['cpu'] += node_resources.get('cpu', 0)
                    sum_resources['memory'] += node_resources.get('memory', 0)
                    sum_resources['gpu'] += node_resources.get('gpu', 0)
            sum_clusters.append((cluster_name, sum_resources))

        clusters = sorted(sum_clusters,
                          key=lambda x: x[1]['cpu'],
                          reverse=True)
        return clusters


# Testing Scheduler Controller.
if __name__ == '__main__':
    controller = SchedulerController()
    controller.run()
