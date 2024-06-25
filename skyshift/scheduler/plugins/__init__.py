"""Init class for Scheduler Plugins."""
from skyshift.scheduler.plugins.cluster_affinity import ClusterAffinityPlugin
from skyshift.scheduler.plugins.cluster_affinity_v2 import \
    ClusterAffinityPluginV2
from skyshift.scheduler.plugins.default_plugin import DefaultPlugin

__all__ = [
    "ClusterAffinityPluginV2",
    "ClusterAffinityPlugin",
    "DefaultPlugin",
]
