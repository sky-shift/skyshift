import logging
import json
import traceback

import requests

from sky_manager.controllers import Controller
from sky_manager.utils import setup_cluster_manager, load_api_service
from sky_manager.api_client.job_api import WatchJobs, DeleteJob


class ExecutionController(Controller):
    """
    Executes and deletes jobs on the cluster.
    """

    def __init__(self, cluster_config) -> None:
        super().__init__()

        self.cluster_config = cluster_config
        self.cluster_name = cluster_config['metadata']['name']
        self.cluster_manager = setup_cluster_manager(cluster_config)

        self.logger = logging.getLogger(
            f'Job \'{self.cluster_name}\' Execution Controller')
        self.logger.setLevel(logging.INFO)

    def run(self):
        # Poll for jobs and execute/kill them depending on the job status.
        host, port = load_api_service()
        for event in WatchJobs():
            try:
                print(event)
                if event['type'] == 'Added':
                    job_object = list(event['object'].values())[0]
                    job_object = json.loads(job_object)
                    if job_object['spec']['cluster'] != self.cluster_name:
                        continue

                    if job_object['spec']['status'] == 'SCHEDULED':
                        try:
                            self.cluster_manager.submit_job(job_object)
                            job_object['spec']['status'] = 'PENDING'
                            requests.post(f'http://{host}:{port}/jobs',
                                          json=job_object)
                        except:
                            print(traceback.print_exc())
                            job_object['spec']['status'] = 'FAILED'
                            requests.post(f'http://{host}:{port}/jobs',
                                          json=job_object)
                    elif job_object['spec']['status'] == 'FAILED':
                        self.cluster_manager.delete_job(job_object)
                elif event['type'] == 'Deleted':
                    # Hack:
                    job_name = list(event['object'].keys())[0]
                    fake_dict = {'metadata': {'name': job_name}}
                    self.cluster_manager.delete_job(fake_dict)
                    DeleteJob(job=job_name)
            except:
                print(traceback.format_exc())
                pass
