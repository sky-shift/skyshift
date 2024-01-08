"""
Each Skylet corresponds to a cluster.

Skylet is a daemon process that runs in the background. It is responsible for updating the state of the cluster and jobs submitted.
"""
import argparse
from copy import deepcopy
import yaml
import os

from skyflow.skylet import *
import traceback

CONTROLLERS = [
    ClusterController,
    FlowController,
    JobController,
    NetworkController,
    ProxyController,
    EndpointsController,
    ServiceController,
]

def launch_skylet(cluster_id):
    controllers = []
    try:
        controllers = []
        for c in CONTROLLERS:
            controllers.append(c(cluster_id))
    except Exception as e:
        print(traceback.format_exc())
        print("Failed to initialize Skylet, check if cluster {cluster_id} is valid.")
    for c in controllers:
        c.start()
    for c in controllers:
        c.join()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Laumch a Skylet for a cluster.")
    parser.add_argument('--config',
                        type=str,
                        required=True,
                        help="Path to the Cluster YAML file.")

    args = parser.parse_args()
    yaml_file_path = args.config

    yaml_file_path = os.path.abspath(yaml_file_path)
    if not os.path.exists(yaml_file_path):
        raise FileNotFoundError(
            f"Cluster config file not found at {yaml_file_path}")
    with open(yaml_file_path, 'r') as f:
        data = yaml.safe_load(f)
    launch_skylet(data)
