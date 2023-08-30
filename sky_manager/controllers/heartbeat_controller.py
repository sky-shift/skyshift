"""
Source code for the log controllers that keep track of the state of the cluster and jobs. These controllers are launched in Skylet.
"""
from copy import deepcopy
import logging
import time

import requests
import traceback

from sky_manager.controllers import Controller
from sky_manager.templates.job_template import Job
from sky_manager.templates.cluster_template import ClusterStatus
from sky_manager.utils import setup_cluster_manager, Informer, load_api_service

CLUSTER_HEARTBEAT_TIME = 3
CLUSTER_RETRY_LIMIT = 3
JOB_HEARTBEAT_TIME = 1
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

    def __init__(self, cluster_config) -> None:
        super().__init__()

        self.cluster_config = cluster_config
        self.cluster_name = cluster_config['metadata']['name']
        self.cluster_manager = setup_cluster_manager(cluster_config)

        # Fetch cluster state template (cached cluster state).
        self.cluster_state = self.cluster_manager.cluster_state

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(
            f'Cluster \'{self.cluster_name}\' Heartbeat Controller')
        self.logger.setLevel(logging.INFO)

    def run(self):
        self.logger.info(
            'Running cluster controller - Updates the state of the cluster.')
        host, port = load_api_service()
        write_url = f'http://{host}:{port}/clusters'
        self.hash = -1
        trigger = 0
        while True:
            start = time.time()
            try:
                self.cluster_state = dict(self.cluster_manager.cluster_state)
                cur_hash = hash(make_dict_hashable(self.cluster_state))
                retry_limit = 0
                trigger += 1
            except Exception as e:
                self.logger.warning(
                    f"Fetching cluster state errored out. Error: {e}. Retrying..."
                )
                retry_limit += 1
                continue
            if retry_limit == CLUSTER_RETRY_LIMIT:
                self.logger.error(
                    f"Cluster {self.cluster_name} seems to be unreachable. Terminating cluster."
                )
                self.cluster_state['spec'][
                    'status'] = ClusterStatus.FAILED.value
            if cur_hash != self.hash or trigger == 8:
                trigger = 0
                response = requests.post(write_url, json=self.cluster_state)
            self.hash = cur_hash
            end = time.time()
            self.logger.info(response)
            if end - start < CLUSTER_HEARTBEAT_TIME:
                time.sleep(CLUSTER_HEARTBEAT_TIME - (end - start))


class JobHeartbeatController(Controller):

    def __init__(self, cluster_config) -> None:
        super().__init__()

        self.cluster_config = cluster_config
        self.cluster_name = cluster_config['metadata']['name']
        self.cluster_manager = setup_cluster_manager(cluster_config)

        # Fetch cluster state template (cached cluster state).
        self.job_state = self.cluster_manager.job_state

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(
            f'Job \'{self.cluster_name}\' Heartbeat Controller')
        self.logger.setLevel(logging.INFO)
        # Keeps track of cached job state.
        self.informer = Informer('jobs')
        self.informer.start()
        time.sleep(1)

    def run(self):
        self.logger.info(
            'Running job controller - Updates the state of the jobs sent by Sky Manager.'
        )

        host, port = load_api_service()
        write_url = f'http://{host}:{port}/jobs'
        while True:
            start = time.time()
            try:
                try:
                    self.job_state = dict(self.cluster_manager.job_state)
                    retry_limit = 0
                except Exception as e:
                    self.logger.warning(
                        f"Fetching job state errored out. Error: {e}. Retrying..."
                    )
                    retry_limit += 1
                    continue
                if retry_limit == JOB_RETRY_LIMIT:
                    self.logger.error(
                        f"Cluster {self.cluster_name} seems to be unreachable. Terminating controller."
                    )
                    break

                informer_object = deepcopy(self.informer.get_object())
                old_status = {
                    k: v['spec']['status']
                    for k, v in informer_object.items()
                }
                for job_name, new_job_status in self.job_state.items():
                    if job_name in old_status and new_job_status == old_status[
                            job_name]:
                        continue
                    if job_name not in old_status:
                        temp_job = Job(name=job_name)
                        temp_job.update_status(new_job_status)
                        temp_job.update_cluster(self.cluster_name)
                    else:
                        temp_job = Job.from_dict(informer_object[job_name])
                        temp_job.update_status(new_job_status)

                    updated_job_dict = dict(temp_job)
                    requests.post(f'{write_url}', json=updated_job_dict)
                end = time.time()
                if end - start < JOB_HEARTBEAT_TIME:
                    time.sleep(JOB_HEARTBEAT_TIME - (end - start))
            except:
                print(traceback.format_exc())
                time.sleep(1)


# if __name__ == '__main__':
#     jc = JobHeartbeatController({
#         'kind': 'Cluster',
#         'metadata': {
#             'name': 'mluo-onprem',
#             'manager_type': 'kubernetes'
#         }
#     })
#     while True:
#         print(jc.informer.object)
#         time.sleep(1)
