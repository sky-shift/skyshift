from multiprocessing import Process
import json
import signal
import subprocess
import tempfile
import time
import traceback
import yaml
import os
import requests

from sky_manager.controllers.controller import Controller
from sky_manager.api_client.cluster_api import WatchClusters
from sky_manager.skylet.skylet import launch_skylet

CONTROLLER_MANAGER_INTERVAL = 1


class SkyletController(Controller):

    def __init__(self):
        self.skylets = {}

    def run(self):
        # Establish a watch over added clusters.
        while True:
            try:
                for data in WatchClusters():
                    if data['type'] == 'Added':
                        cluster_config = list(data['object'].values())[0]
                        cluster_config = json.loads(cluster_config)
                        cluster_name = cluster_config['metadata']['name']
                        print(cluster_config)
                        if cluster_name in self.skylets or cluster_config[
                                'spec']['status'] != 'INIT':
                            continue
                        # Launch a Skylet to manage the cluster state.
                        skylet_process = Process(target=launch_skylet,
                                                 args=(cluster_config, ))
                        skylet_process.start()
                        self.skylets[cluster_name] = skylet_process
                    elif data['type'] == 'Deleted':
                        if cluster_name not in self.skylets:
                            continue
                        cluster_name = list(data['object'].keys())[0]
                        self.skylets[cluster_name].terminate()
                        del self.skylets[cluster_name]
            except requests.exceptions.ConnectionError as e:
                traceback.print_exc()
                print('API Server closed. Restarting Controller.')
            except Exception as e:
                traceback.print_exc()
                time.sleep(1)


if __name__ == '__main__':
    a = SkyletController()
    a.run()