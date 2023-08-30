import json
import time
import traceback
from copy import deepcopy

from concurrent.futures import ThreadPoolExecutor, wait
import requests

from sky_manager.controllers import Controller
from sky_manager.utils import Informer, load_api_service
from sky_manager.api_client.job_api import WatchJobs
from sky_manager.api_client.cluster_api import WatchClusters


class SchedulerController(Controller):
    """
    Figures out the best cluster to place a job on.
    """

    def __init__(self) -> None:
        super().__init__()
        self.cluster_informer = Informer('clusters')
        self.cluster_informer.start()
        # Assumed FIFO
        self.queue = []

    def run(self):
        # Poll for jobs and execute/kill them depending on the job status.
        host, port = load_api_service()
        for event in merge_gens(WatchClusters(), WatchJobs()):
            try:
                #print(event)
                event_type = event['type']
                object_value = list(event['object'].values())[0]
                if event_type != 'Added':
                    continue

                object_value = json.loads(object_value)
                # Only add jobs that have new arrived or failed over from a prior cluster.
                if object_value['kind'] == 'Job':
                    if object_value['spec']['status'] in ['INIT']:
                        self.queue.append(object_value)
                    else:
                        continue
                if len(self.queue) == 0:
                    continue

                # Main Scheduling loop.
                # Local cache of clusters for this scheduling loop.
                clusters = deepcopy(self.cluster_informer.get_object())
                clusters = tuple(clusters.items())
                sched_jobs = []
                for job in self.queue:
                    filtered_clusters = self.filter_clusters(job, clusters)
                    ranked_clusters = self.rank_clusters(
                        job, filtered_clusters)
                    if clusters:
                        # Fetch the top scoring cluster.
                        job['spec']['cluster'] = ranked_clusters[0][0]
                        job['spec']['status'] = 'SCHEDULED'
                        response = requests.post(f'http://{host}:{port}/jobs',
                                                 json=job)
                        print(response.json())
                        sched_jobs.append(job)
                for sched_job in sched_jobs:
                    self.queue.remove(sched_job)
            except:
                print(traceback.format_exc())
                time.sleep(1)

    def filter_clusters(self, job, clusters):
        # For now there is NO filter.
        return clusters

    def rank_clusters(self, job, clusters):
        # For now this policy is rank cluster by their availability". (most resources)
        sum_clusters = []
        for cluster in clusters:
            cluster_name, cluster_dict = cluster
            resources = cluster_dict['spec']['allocatable_resources']
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


def merge_gens(gen1, gen2):
    with ThreadPoolExecutor(max_workers=2) as executor:
        gen1_next = executor.submit(next, gen1, None)
        gen2_next = executor.submit(next, gen2, None)

        while True:
            # Wait for one of the generators to produce a result
            done, _ = wait([gen1_next, gen2_next],
                           return_when='FIRST_COMPLETED')

            for future in done:
                result = future.result()
                if result is not None:
                    yield result
                    # Re-submit the task for the generator(s) that have completed.
                    if gen1_next in done:
                        gen1_next = executor.submit(next, gen1, None)
                    if gen2_next in done:
                        gen2_next = executor.submit(next, gen2, None)


# Testing Scheduler Controller.
if __name__ == '__main__':
    controller = SchedulerController()
    controller.run()
