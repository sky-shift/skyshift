"""Init class for Scheduler Plugins."""
from skyflow.scheduler.plugins.cluster_affinity import ClusterAffinityPlugin
from skyflow.scheduler.plugins.cluster_affinity_v2 import ClusterAffinityPluginV2
from skyflow.scheduler.plugins.default_plugin import DefaultPlugin

__all__ = [
    "ClusterAffinityPluginV2"
    "ClusterAffinityPlugin",
    "DefaultPlugin",
]
