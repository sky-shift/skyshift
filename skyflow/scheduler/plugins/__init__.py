"""Init class for Scheduler Plugins."""
from skyflow.scheduler.plugins.cluster_affinity import ClusterAffinityPlugin
from skyflow.scheduler.plugins.default_plugin import DefaultPlugin

__all__ = [
    "ClusterAffinityPlugin",
    "DefaultPlugin",
]
