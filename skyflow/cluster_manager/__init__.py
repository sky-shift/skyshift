"""
Instantiates the compatability layer across cluster managers.
"""
from skyflow.cluster_manager.kubernetes.kubernetes_manager import \
    KubernetesManager
from skyflow.cluster_manager.manager import Manager
from skyflow.cluster_manager.manager_utils import setup_cluster_manager
from skyflow.cluster_manager.ray.ray_manager import RayManager
from skyflow.cluster_manager.slurm.slurm_manager_cli import SlurmManagerCLI
from skyflow.cluster_manager.slurm.slurm_manager_rest import SlurmManagerREST

__all__ = [
    "Manager", "KubernetesManager", "RayManager", "setup_cluster_manager",
    "SlurmManagerREST", "SlurmManagerCLI"
]
