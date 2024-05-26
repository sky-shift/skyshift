"""
Each Skylet corresponds to a cluster.

Skylet is a daemon process that runs in the background.
It is responsible for updating the state of the cluster and jobs submitted.
"""

import argparse
import os
import traceback

import yaml

from skyflow.cluster_manager.manager import K8_MANAGERS
from skyflow.skylet import (ClusterController, EndpointsController,
                            FlowController, JobController, NetworkController,
                            ProxyController, ServiceController)
from skyflow.templates.cluster_template import Cluster


BASE_CONTROLLERS = [
    ClusterController,
    FlowController,
    JobController,
]

SERVICE_CONTROLLERS = [
    NetworkController,
    ProxyController,
    EndpointsController,
    ServiceController,
]


def launch_skylet(cluster_obj: Cluster):
    """
    Launches a Skylet for a given cluster.
    """
    cluster_id = cluster_obj.metadata.name
    cluster_type = cluster_obj.spec.manager
    controllers = []

    controller_types = BASE_CONTROLLERS
    if cluster_type in K8_MANAGERS:
        controller_types.extend(SERVICE_CONTROLLERS)

    for cont in controller_types:
        try:
            controllers.append(cont(cluster_id))
        except Exception:  # pylint: disable=broad-except
            print(traceback.format_exc())
            print(f"Failed to initialize Skylet controller {cont}, "
                f"check if cluster {cluster_id} is valid.")

    for cont in controllers:
        cont.start()
    for cont in controllers:
        cont.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Launch a Skylet for a cluster.")
    parser.add_argument("--config",
                        type=str,
                        required=True,
                        help="Path to the Cluster YAML file.")

    args = parser.parse_args()
    yaml_file_path = args.config

    yaml_file_path = os.path.abspath(yaml_file_path)
    if not os.path.exists(yaml_file_path):
        raise FileNotFoundError(
            f"Cluster config file not found at {yaml_file_path}")
    with open(yaml_file_path, "r") as f:
        data = yaml.safe_load(f)
    launch_skylet(data)
