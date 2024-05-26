"""
Each Skylet corresponds to a cluster.

Skylet is a daemon process that runs in the background.
It is responsible for updating the state of the cluster and jobs submitted.
"""
import traceback
from typing import List, Type

from skyflow.controllers import Controller
from skyflow.globals import K8_MANAGERS
from skyflow.skylet import (ClusterController, EndpointsController,
                            FlowController, JobController, NetworkController,
                            ProxyController, ServiceController)
from skyflow.templates import Cluster

BASE_CONTROLLERS: List[Type[Controller]] = [
    ClusterController,
    FlowController,
    JobController,
]
SERVICE_CONTROLLERS: List[Type[Controller]] = [
    NetworkController,
    ProxyController,
    EndpointsController,
    ServiceController,
]


def launch_skylet(cluster_obj: Cluster):
    """
    Launches a Skylet for a given cluster.
    """
    cluster_id: str = cluster_obj.metadata.name
    cluster_type: str = cluster_obj.spec.manager

    controller_types: List[Type[Controller]] = BASE_CONTROLLERS
    if cluster_type in K8_MANAGERS:
        controller_types.extend(SERVICE_CONTROLLERS)

    controllers: List[Controller] = []
    for cont in controller_types:
        try:
            init_controller: Controller = cont(cluster_id)
            controllers.append(init_controller)
        except Exception:  # pylint: disable=broad-except
            print(traceback.format_exc())
            print(f"Failed to initialize Skylet controller {cont}, "
                  f"check if cluster {cluster_id} is valid.")

    for controller in controllers:
        controller.start()
    for controller in controllers:
        controller.join()
