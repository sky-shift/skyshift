"""
Instantiates the compatability layer across cluster managers.
"""
from skyflow.cluster_manager.Kubernetes.kubernetes_manager import KubernetesManager
from skyflow.cluster_manager.Ray.ray_manager import RayManager
from skyflow.cluster_manager.manager import Manager
from skyflow.cluster_manager.manager_utils import setup_cluster_manager

__all__ = [
    "Manager",
    "KubernetesManager",
    "RayManager",
    "setup_cluster_manager",
]
