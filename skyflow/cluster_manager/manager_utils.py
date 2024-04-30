# pylint: disable=E1101
"""
Utils for cluster managers.
"""
import logging
import os
from typing import Union

import yaml

from skyflow.cluster_manager.kubernetes_manager import KubernetesManager
from skyflow.cluster_manager.slurm_manager_cli import SlurmManagerCLI
from skyflow.cluster_manager.slurm_manager_rest import SlurmManagerREST
from skyflow.templates.cluster_template import Cluster
from skyflow.utils import *
from skyflow.utils.slurm_utils import (VerifySlurmConfig, SlurmInterfaceEnum)
from skyflow.globals import KUBERNETES_ALIASES
from skyflow.globals import SLURM_ALIASES
from skyflow.globals import SUPPORTED_MANAGERS

from skyflow.globals import SLURM_CONFIG_PATH

logging.basicConfig(
    level=logging.INFO,
    format="%(name)s - %(asctime)s - %(levelname)s - %(message)s")


class ConfigUndefinedError(Exception):
    """ Raised when there is an error in slurm config yaml. """


def setup_cluster_manager(
    cluster_obj: Cluster
) -> Union[KubernetesManager, SlurmManagerREST, SlurmManagerCLI]:
    """ Assigns cluster manager depending on requested type.

        Args:
            cluster_obj: CLI requested cluster object to be created.

        Returns:
            Instance of the desired cluster manager class.

    """
    cluster_type = cluster_obj.spec.manager.lower()
    if cluster_type not in SUPPORTED_MANAGERS:
        raise ValueError(f"Cluster type {cluster_type} not supported.")
    if cluster_type in KUBERNETES_ALIASES:
        k8s_manager_cls = KubernetesManager
    elif cluster_type in SLURM_ALIASES:
        #Get the cluster name to correspond it to nested yaml keys
        cluster_name = str(cluster_obj.metadata.name)
        #Get the manager interface type
        SlurmConfig = VerifySlurmConfig()
        SlurmConfig.verify_configuration(cluster_name)
        interface_type = SlurmConfig.interface_type

        if interface_type == SlurmInterfaceEnum.REST:
            slurm_manager_rest_cls = SlurmManagerREST
            # Get the constructor of the class
            slurm_constructor = slurm_manager_rest_cls.__init__
            # Get the parameter names of the constructor
            class_params = slurm_constructor.__code__.co_varnames[
                1:slurm_constructor.__code__.co_argcount]

            # Filter the dictionary keys based on parameter names
            args = {
                k: v
                for k, v in dict(cluster_obj.metadata).items()
                if k in class_params
            }
            # Create an instance of the class with the extracted arguments.
            return slurm_manager_rest_cls(**args)

        slurm_manager_cli_cls = SlurmManagerCLI
        # Get the constructor of the class
        slurm_manager_cli_cls.cluster_name = cluster_name
        slurm_constructor_cli = slurm_manager_cli_cls.__init__
        # Get the parameter names of the constructor
        class_params = slurm_constructor_cli.__code__.co_varnames[
            1:slurm_constructor_cli.__code__.co_argcount]

        # Filter the dictionary keys based on parameter names
        args = {
            k: v
            for k, v in dict(cluster_obj.metadata).items() if k in class_params
        }
        # Create an instance of the class with the extracted arguments.
        return slurm_manager_cli_cls(**args)
    #KubernetesManager
    # Get the constructor of the class
    k8s_manager_cls = KubernetesManager
    k8s_constructor = k8s_manager_cls.__init__
    # Get the parameter names of the constructor
    class_params = k8s_constructor.__code__.co_varnames[1:k8s_constructor.__code__.
                                                    co_argcount]

    args = {
            k: v
            for k, v in dict(cluster_obj.metadata).items() if k in class_params
        }
    # Filter the dictionary keys based on parameter names
    args.update({
        k: v
        for k, v in dict(cluster_obj.metadata).items() if k in class_params
    })

    logger = logging.getLogger(
        f"[{cluster_obj.metadata.name} - {cluster_type} Manager]")
    # Create an instance of the class with the extracted arguments.
    return k8s_manager_cls(**args)
