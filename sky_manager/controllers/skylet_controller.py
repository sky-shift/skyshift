from multiprocessing import Process
import json
import psutil
import time
import traceback
import requests

from sky_manager.controllers.controller import Controller
from sky_manager.api_client.cluster_api import WatchClusters
from sky_manager.skylet.skylet import launch_skylet
from sky_manager.templates.cluster_template import ClusterStatusEnum

CONTROLLER_MANAGER_INTERVAL = 1


def terminate_process_and_children(pid):
    parent = psutil.Process(pid)
    for child in parent.children(recursive=True):
        child.terminate()
    parent.terminate()


class SkyletController(Controller):

    def __init__(self):
        self.skylets = {}

    def run(self):
        # Establish a watch over added clusters.
        while True:
            try:
                for data in WatchClusters():
                    # If Cluster has been added/updated, check if the cluster is in INIT state.
                    if data['type'] == 'Added':
                        cluster_config = list(data['object'].values())[0]
                        cluster_config = json.loads(cluster_config)
                        cluster_name = cluster_config['metadata']['name']
                        if cluster_name in self.skylets or cluster_config[
                                'status'][
                                    'status'] != ClusterStatusEnum.INIT.value:
                            continue

                        # Launch a Skylet to manage the cluster state.
                        skylet_process = Process(target=launch_skylet,
                                                 args=(cluster_config, ))
                        skylet_process.start()
                        self.skylets[cluster_name] = skylet_process

                    # If Cluster has been deleted, terminate Skylet corresponding to the cluster.
                    if data['type'] == 'Deleted':
                        if cluster_name not in self.skylets:
                            continue
                        cluster_name = list(data['object'].keys())[0]
                        terminate_process_and_children(
                            self.skylets[cluster_name].pid)
                        # self.skylets[cluster_name].terminate()
                        del self.skylets[cluster_name]
            except requests.exceptions.ConnectionError as e:
                traceback.print_exc()
                print('Cannot seem to connect to API server, trying again...')
            except Exception as e:
                traceback.print_exc()
            time.sleep(CONTROLLER_MANAGER_INTERVAL)


if __name__ == '__main__':
    a = SkyletController()
    a.run()