"""
Utils for cluster managers.
"""
import logging

from skyflow.cluster_manager.kubernetes_manager import KubernetesManager
from skyflow.cluster_manager.manager import K8_MANAGERS, RAY_MANAGERS
from skyflow.cluster_manager.ray_manager import RayManager
from skyflow.templates import Cluster

logging.basicConfig(
    level=logging.INFO,
    format="%(name)s - %(asctime)s - %(levelname)s - %(message)s")


def setup_cluster_manager(cluster_obj: Cluster):
    """
    Discovers and creates the appropriate cluster manager instance based on the
    cluster object.
    """
    cluster_type = cluster_obj.spec.manager

    args = {}

    if cluster_type in K8_MANAGERS:
        cluster_manager_cls = KubernetesManager
        args["config_path"] = cluster_obj.spec.config_path
    elif cluster_type in RAY_MANAGERS:
        cluster_manager_cls = RayManager
        args["ssh_key_path"] = cluster_obj.spec.ssh_key_path
        args["username"] = cluster_obj.spec.username
        args["host"] = cluster_obj.spec.host
    else:
        raise ValueError(f"Cluster type {cluster_type} not supported.")

    # Get the constructor of the class
    constructor = cluster_manager_cls.__init__
    # Get the parameter names of the constructor
    class_params = constructor.__code__.co_varnames[1:constructor.__code__.
                                                    co_argcount]
    print(class_params)
    # Filter the dictionary keys based on parameter names
    args.update({
        k: v
        for k, v in dict(cluster_obj.metadata).items() if k in class_params
    })

    logger = logging.getLogger(
        f"[{cluster_obj.metadata.name} - {cluster_type} Manager]")
    # Create an instance of the class with the extracted arguments.
    print(args)
    manager = cluster_manager_cls(logger=logger, **args)
    print(manager)
    return manager
