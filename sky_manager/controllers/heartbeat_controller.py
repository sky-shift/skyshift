"""
Source code for the log controllers that keep track of the state of the cluster and jobs. These controllers are launched in Skylet.
"""
from copy import deepcopy
import logging
import time

import requests
import traceback

from sky_manager.controllers import Controller
from sky_manager.templates.job_template import Job, JobStatusEnum
from sky_manager.templates.cluster_template import Cluster, ClusterStatus, ClusterStatusEnum
from sky_manager.utils import setup_cluster_manager, Informer, load_api_service
from sky_manager.api_client import *

CLUSTER_HEARTBEAT_TIME = 5
CLUSTER_RETRY_LIMIT = 3
JOB_HEARTBEAT_TIME = 3
JOB_RETRY_LIMIT = 3


def make_dict_hashable(d):
    if isinstance(d, dict):
        return frozenset((k, make_dict_hashable(v)) for k, v in d.items())
    elif isinstance(d, list):
        return tuple(make_dict_hashable(item) for item in d)
    elif isinstance(d, set):
        return frozenset(make_dict_hashable(item) for item in d)
    else:
        return d


class ClusterHeartbeatController(Controller):
    """
    Regularly polls the cluster for its status and updates the API server of the latest status.

    The status includes the cluster capacity, allocatable capacity, and the current status of the cluster.
    """

    def __init__(self, cluster_config) -> None:
        super().__init__()
        self.cluster_obj = Cluster.from_dict(cluster_config)
        self.cluster_manager = setup_cluster_manager(self.cluster_obj)
        self.cluster_name = self.cluster_obj.meta.name
        self.cluster_status = self.cluster_manager.get_cluster_status()

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(
            f'[{self.cluster_name}] Cluster Heartbeat Controller')
        self.logger.setLevel(logging.INFO)

    def run(self):
        self.logger.info(
            'Running cluster controller - Updates the state of the cluster.')
        self.cluster_api = ClusterAPI()
        while True:
            start = time.time()

            try:
                self.cluster_status = self.cluster_manager.get_cluster_status()
                retry_limit = 0
            except Exception as e:
                self.logger.warning(
                    f"Fetching cluster state errored out. Error: {e}. Retrying..."
                )
                retry_limit += 1
                continue
            if retry_limit == CLUSTER_RETRY_LIMIT:
                self.logger.error(
                    f"Cluster {self.cluster_name} seems to be unreachable. Terminating controller."
                )
                self.cluster_status.update_status(
                    ClusterStatusEnum.ERROR.value)
            self._update_cluster_state(self.cluster_status)
            self.logger.info('Updated cluster state.')

            end = time.time()
            if end - start < CLUSTER_HEARTBEAT_TIME:
                time.sleep(CLUSTER_HEARTBEAT_TIME - (end - start))

    def _update_cluster_state(self, cluster_status: ClusterStatus):
        host, port = load_api_service()
        api_server_url = f'http://{host}:{port}/clusters'

        cluster_exists = False
        try:
            response = self.cluster_api.Get(self.cluster_name)
            cluster_obj = Cluster.from_dict(response)
            cluster_exists = True
        except Exception as e:
            cluster_obj = self.cluster_obj

        prev_cluster_status = cluster_obj.status
        prev_cluster_status.update_status(cluster_status.curStatus)
        prev_cluster_status.update_capacity(cluster_status.capacity)
        prev_cluster_status.update_allocatable_capacity(
            cluster_status.allocatable_capacity)
        if not cluster_exists:
            self.cluster_api.Create(dict(cluster_obj))
        else:
            self.cluster_api.Update(dict(cluster_obj))


class JobHeartbeatController(Controller):

    def __init__(self, cluster_config) -> None:
        super().__init__()

        self.cluster_obj = Cluster.from_dict(cluster_config)
        self.cluster_manager = setup_cluster_manager(self.cluster_obj)
        self.cluster_name = self.cluster_obj.meta.name
        # Fetch cluster state template (cached cluster state).
        self.job_status = self.cluster_manager.get_jobs_status()

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(
            f'[{self.cluster_name}] Job Heartbeat Controller')
        self.logger.setLevel(logging.INFO)
        # Keeps track of cached job state.
        self.informer = Informer('jobs')
        self.informer.start()
        time.sleep(1)

    def run(self):
        self.logger.info(
            'Running job controller - Updates the status of the jobs sent by Sky Manager.'
        )
        self.job_api = JobAPI()
        while True:
            start = time.time()
            try:
                try:
                    self.job_status = self.cluster_manager.get_jobs_status()
                    retry_limit = 0
                except Exception as e:
                    self.logger.info(
                        f"Fetching job state errored out. Error: {e}. Retrying..."
                    )
                    retry_limit += 1
                    continue
                if retry_limit == JOB_RETRY_LIMIT:
                    self.logger.info(
                        f"Cluster {self.cluster_name} seems to be unreachable. Trying again..."
                    )
                    break

                # Copy Informer to get the current job statuses.
                informer_object = deepcopy(self.informer.get_cache())
                prev_status = {
                    k: v['status']['status']
                    for k, v in informer_object.items()
                }
                for job_name, new_job_status in self.job_status.items():
                    if job_name not in prev_status:
                        temp_job = Job(meta={
                            'name': job_name,
                        })
                        temp_job.status.update_status(new_job_status.curStatus)
                        temp_job.status.update_cluster(self.cluster_name)
                        continue

                    # Save API calls.
                    if new_job_status.curStatus == JobStatusEnum.COMPLETED.value and prev_status[
                            job_name] == new_job_status.curStatus:
                        continue

                    temp_job = Job.from_dict(informer_object[job_name])
                    temp_job.status.update_status(new_job_status.curStatus)
                    try:
                        self.job_api.Update(config=dict(temp_job),
                                            namespace=temp_job.meta.namespace)
                    except Exception as e:
                        self.job_api.Create(config=dict(temp_job),
                                            namespace=temp_job.meta.namespace)
                end = time.time()
                if end - start < JOB_HEARTBEAT_TIME:
                    time.sleep(JOB_HEARTBEAT_TIME - (end - start))
            except:
                print(traceback.format_exc())
                time.sleep(1)


# if __name__ == '__main__':
#     hc = ClusterHeartbeatController({
#         'kind': 'Cluster',
#         'metadata': {
#             'name': 'mluo-onprem',
#         },
#         'spec': {
#             'manager': 'kubernetes',
#         }
#     })
#     hc.run()
if __name__ == '__main__':
    jc = JobHeartbeatController({
        'kind': 'Cluster',
        'metadata': {
            'name': 'mluo-onprem',
        },
        'spec': {
            'manager': 'kubernetes',
        }
    })
    jc.run()
    # while True:
    #     print(jc.informer.get_cache())
    #     time.sleep(1)
