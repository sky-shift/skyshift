from copy import deepcopy
from queue import Queue
import logging
import traceback
import time

from sky_manager.utils import Informer
from sky_manager.controllers import Controller
from sky_manager.utils import setup_cluster_manager
from sky_manager.templates.job_template import Job, JobStatusEnum
from sky_manager.templates.cluster_template import Cluster
from sky_manager.api_client import *

CONTROLLER_RATE_LIMIT = 0.2


class ExecutionController(Controller):
    """
    The Execution controller determines the flow of jobs in and out of the cluster.
    """

    def __init__(self, cluster_config) -> None:
        self.cluster_obj = Cluster.from_dict(cluster_config)
        self.cluster_manager = setup_cluster_manager(self.cluster_obj)
        self.cluster_name = self.cluster_obj.meta.name

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        self.logger = logging.getLogger(
            f'[{self.cluster_name}] Execution Controller')
        self.logger.setLevel(logging.INFO)

        self.worker_queue = Queue()

        super().__init__()

        # self.policy_informer = Informer('filterpolicies')

        # def add_policy_callback_fn(event):
        #     self.worker_queue.put(event)

        # self.policy_informer.add_event_callbacks(
        #     add_event_callback=add_policy_callback_fn,
        #     delete_event_callback=None)
        # self.policy_informer.start()

    def post_init_hook(self):
        # Python thread safe queue for Informers to append events to.
        self.job_informer = Informer('jobs')

        def add_callback_fn(event):
            event_object = event[1]
            # Filter for jobs that are scheduled by the Scheduler Controller and
            # are assigned to this cluster.
            if event_object['status'][
                    'cluster'] == self.cluster_name and event_object['status'][
                        'status'] == 'SCHEDULED':
                self.worker_queue.put(event)

        def delete_callback_fn(event):
            self.worker_queue.put(event)

        # Filtered add events and delete events are added to the worker queue.
        self.job_informer.add_event_callbacks(
            add_event_callback=add_callback_fn,
            delete_event_callback=delete_callback_fn)
        self.job_informer.start()

    def run(self):
        # Poll for jobs and execute/kill them depending on the job status.
        self.logger.info(
            'Running execution controller - Manages job submission and eviction from the cluster.'
        )
        job_api_object = JobAPI()
        # Run Forever
        while True:
            # Blocks until there is at least 1 element in the queue.
            event = self.worker_queue.get()
            try:
                event_key = event[0]
                event_object = event[1]
                cached_jobs = deepcopy(self.job_informer.get_cache())

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

                # Handler for Job Events
                if event_key in cached_jobs:
                    # Add Event
                    job_object = Job.from_dict(event_object)
                    try:
                        self.logger.info(
                            f'Submitting job \'{job_object.meta.name}\' to cluster \'{self.cluster_name}\'.'
                        )
                        self.cluster_manager.submit_job(job_object)
                        job_object.status.update_status(
                            JobStatusEnum.PENDING.value)
                    except:
                        traceback.print_exc()
                        self.logger.info(
                            f'Failed to submit job  \'{job_object.meta.name}\' to the cluster  \'{self.cluster_name}\'. Marking job as failed.'
                        )
                        job_object.status.update_status(
                            JobStatusEnum.FAILED.value)
                        job_object.meta.annotations[
                            self.
                            cluster_name] = 'reason:job-submission-failure'
                    job_api_object = JobAPI()
                    job_api_object.Update(config=dict(job_object),
                                          namespace=job_object.meta.namespace)
                else:
                    # Delete Event (object is gone from Informer cache).
                    # Bug: Deleted jobs have an empty event_object field.
                    # TODO(mluo); Monkeypatch ETCD Client to return deleted object.
                    fake_dict = {
                        'kind': 'Job',
                        'metadata': {
                            'name': event_key
                        }
                    }
                    self.cluster_manager.delete_job(Job.from_dict(fake_dict))
            except:
                self.logger.info('Failed to process job event.')
                print(traceback.format_exc())
            self.worker_queue.task_done()
            time.sleep(CONTROLLER_RATE_LIMIT)


if __name__ == '__main__':
    jc = ExecutionController({
        'kind': 'Cluster',
        'metadata': {
            'name': 'mluo-onprem',
        },
        'spec': {
            'manager': 'kubernetes',
        }
    })
    jc.run()
