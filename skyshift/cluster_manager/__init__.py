"""
Instantiates the compatability layer across cluster managers.
"""
from skyshift.cluster_manager.kubernetes.kubernetes_manager import \
    KubernetesManager
from skyshift.cluster_manager.manager import Manager
from skyshift.cluster_manager.manager_utils import setup_cluster_manager
from skyshift.cluster_manager.ray.ray_manager import RayManager
from skyshift.cluster_manager.slurm.slurm_manager_cli import SlurmManagerCLI
from skyshift.cluster_manager.slurm.slurm_manager_rest import SlurmManagerREST

__all__ = [
    "Manager", "KubernetesManager", "RayManager", "setup_cluster_manager",
    "SlurmManagerREST", "SlurmManagerCLI"
]
