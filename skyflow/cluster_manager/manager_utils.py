"""
Utils for cluster managers.
"""
from typing import Union

from skyflow.cluster_manager.kubernetes_manager import KubernetesManager
from skyflow.cluster_manager.slurm_manager import SlurmManager
from skyflow.templates.cluster_template import Cluster

KUBERNETES_ALIASES = ("kubernetes", "k8", "k8s")
SLURM_ALIASES = ("slurm", "slurmctl")
SUPPORTED_MANAGERS = KUBERNETES_ALIASES + SLURM_ALIASES


def setup_cluster_manager(
        cluster_obj: Cluster) -> Union[KubernetesManager, SlurmManager]:
    """ Assigns cluster manager depending on requested type.

        Args:
            cluster_obj: CLI requested cluster object to be created.

        Returns:
            Instance of the desired cluster manager class.

    """
    is_slurm_manager = False
    cluster_type = cluster_obj.spec.manager.lower()
    if cluster_type not in SUPPORTED_MANAGERS:
        raise ValueError(f"Cluster type {cluster_type} not supported.")
    if cluster_type in KUBERNETES_ALIASES:
        k8s_manager_cls = KubernetesManager
    elif cluster_type in SLURM_ALIASES:
        slurm_manager_cls = SlurmManager
        is_slurm_manager = True

    if is_slurm_manager:
        # Get the constructor of the class
        slurm_constructor = slurm_manager_cls.__init__
        # Get the parameter names of the constructor
        class_params = slurm_constructor.__code__.co_varnames[
            1:slurm_constructor.__code__.co_argcount]

        # Filter the dictionary keys based on parameter names
        args = {
            k: v
            for k, v in dict(cluster_obj.metadata).items() if k in class_params
        }
        # Create an instance of the class with the extracted arguments.
        return slurm_manager_cls(**args)
    #KubernetesManager
    # Get the constructor of the class
    constructor = k8s_manager_cls.__init__
    # Get the parameter names of the constructor
    class_params = constructor.__code__.co_varnames[1:constructor.__code__.
                                                    co_argcount]

    # Filter the dictionary keys based on parameter names
    args = {
        k: v
        for k, v in dict(cluster_obj.metadata).items() if k in class_params
    }
    # Create an instance of the class with the extracted arguments.
    return k8s_manager_cls(**args)
