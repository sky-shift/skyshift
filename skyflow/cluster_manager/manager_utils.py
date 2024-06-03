# pylint: disable=E1101
"""
This module contains utility functions for the ray cluster manager.
"""
import logging
from typing import Type

from skyflow.cluster_manager.kubernetes import KubernetesManager
from skyflow.cluster_manager.manager import Manager
from skyflow.cluster_manager.ray.ray_manager import RayManager
from skyflow.cluster_manager.slurm import SlurmManagerCLI, SlurmManagerREST
from skyflow.cluster_manager.slurm.slurm_utils import (SlurmConfig,
                                                       SlurmInterfaceEnum)
from skyflow.globals import (K8_MANAGERS, RAY_MANAGERS, SLURM_MANAGERS,
                             SUPPORTED_MANAGERS)
from skyflow.templates import Cluster

logging.basicConfig(
    level=logging.INFO,
    format="%(name)s - %(asctime)s - %(levelname)s - %(message)s")


def setup_cluster_manager(cluster_obj: Cluster) -> Manager:
    """ Assigns cluster manager depending on requested type.

        Args:
            cluster_obj: CLI requested cluster object to be created.

        Returns:
            Instance of the desired cluster manager class.

    """
    cluster_type = cluster_obj.spec.manager.lower()
    cluster_name = cluster_obj.get_name()
    if cluster_type not in SUPPORTED_MANAGERS:
        raise ValueError(f"Cluster type {cluster_type} not supported.")

    args = {}
    cluster_manager_cls: Type[Manager] = Manager
    if cluster_type in K8_MANAGERS:
        cluster_manager_cls = KubernetesManager
        args["config_path"] = cluster_obj.spec.config_path
    elif cluster_type in SLURM_MANAGERS:
        args["config_path"] = cluster_obj.spec.config_path
        slurm_config = SlurmConfig(config_path=args["config_path"])
        interface_type = slurm_config.get_interface(cluster_name)
        if interface_type == SlurmInterfaceEnum.REST.value:
            cluster_manager_cls = SlurmManagerREST
        elif interface_type == SlurmInterfaceEnum.CLI.value:
            cluster_manager_cls = SlurmManagerCLI
        else:
            raise ValueError(f"Unsupported Slurm interface: {interface_type}")
    elif cluster_type in RAY_MANAGERS:
        cluster_manager_cls = RayManager
        args["ssh_key_path"] = cluster_obj.spec.ssh_key_path
        args["username"] = cluster_obj.spec.username
        args["host"] = cluster_obj.spec.host

    # Get the constructor of the class
    constructor = cluster_manager_cls.__init__
    # Get the parameter names of the constructor
    class_params = constructor.__code__.co_varnames[1:constructor.__code__.
                                                    co_argcount]
    # Filter the dictionary keys based on parameter names
    args.update({
        k: v
        for k, v in dict(cluster_obj.metadata).items() if k in class_params
    })
    logger = logging.getLogger(f"[{cluster_name} - {cluster_type} Manager]")
    # Create an instance of the class with the extracted arguments.
    manager = cluster_manager_cls(logger=logger, **args)
    return manager
