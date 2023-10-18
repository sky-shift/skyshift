import logging
import json
import traceback
import time

import requests

from sky_manager.controllers import Controller
from sky_manager.utils import setup_cluster_manager, load_api_service
from sky_manager.api_client.job_api import WatchJobs, DeleteJob
from sky_manager.templates.job_template import Job, JobStatusEnum
from sky_manager.templates.cluster_template import Cluster


class ExecutionController(Controller):
    """
    Executes and deletes jobs on the cluster.
    """

    def __init__(self, cluster_config) -> None:
        super().__init__()

        self.cluster_obj = Cluster.from_dict(cluster_config)
        self.cluster_manager = setup_cluster_manager(self.cluster_obj)
        self.cluster_name = self.cluster_obj.meta.name

        self.logger = logging.getLogger(
            f'Job \'{self.cluster_name}\' Execution Controller')
        self.logger.setLevel(logging.INFO)

    def run(self):
        # Poll for jobs and execute/kill them depending on the job status.
        host, port = load_api_service()
        self.logger.info(
            'Running execution controller - Manages job submission and eviction from the cluster.'
        )
        while True:
            for event in WatchJobs():
                try:
                    if event['type'] == 'Added':
                        job_object = list(event['object'].values())[0]
                        job_object = json.loads(job_object)
                        job_object = Job.from_dict(job_object)

                        if job_object.status.cluster != self.cluster_name:
                            continue

                        if job_object.status.curStatus == 'SCHEDULED':
                            try:
                                self.logger.info(
                                    f'Submitting job \'{job_object.meta.name}\' to the cluster \'{self.cluster_name}\'.'
                                )
                                self.cluster_manager.submit_job(job_object)
                                job_object.status.update_status(
                                    JobStatusEnum.PENDING.value)
                            except:
                                self.logger.info(
                                    'Failed to submit job to the cluster. Marking job as failed.'
                                )
                                print(traceback.print_exc())
                                job_object.status.update_status(
                                    JobStatusEnum.FAILED.value)
                                job_object.meta.annotations[
                                    self.
                                    cluster_name] = 'job-submission-failure'
                            requests.post(f'http://{host}:{port}/jobs',
                                          json=dict(job_object))
                    elif event['type'] == 'Deleted':
                        # Hack:
                        job_name = list(event['object'].keys())[0]
                        fake_dict = {
                            'kind': 'Job',
                            'metadata': {
                                'name': job_name
                            }
                        }
                        self.cluster_manager.delete_job(
                            Job.from_dict(fake_dict))
                except:
                    print(traceback.format_exc())
                    time.sleep(1)


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
