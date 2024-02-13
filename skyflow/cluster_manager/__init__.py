"""
Instantiates the compatability layer across cluster managers.
"""
from skyflow.cluster_manager.kubernetes_manager import KubernetesManager
from skyflow.cluster_manager.manager import Manager
from skyflow.cluster_manager.manager_utils import setup_cluster_manager
from skyflow.cluster_manager.slurm_manager import SlurmManager

__all__ = [
    "Manager", "KubernetesManager", "setup_cluster_manager", "SlurmManager"
]
