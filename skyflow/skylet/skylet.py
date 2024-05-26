"""
Each Skylet corresponds to a cluster.

Skylet is a daemon process that runs in the background.
It is responsible for updating the state of the cluster and jobs submitted.
"""

import argparse
import os
import traceback

import yaml

from skyflow.globals import K8_MANAGERS
from skyflow.skylet import (ClusterController, EndpointsController,
                            FlowController, JobController, NetworkController,
                            ProxyController, ServiceController)
from skyflow.templates import Cluster

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
