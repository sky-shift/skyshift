"""
Specifies the default scheduler plugin for the SchedulerController.
"""
from copy import deepcopy
from typing import Dict, List, Tuple

from skyflow.scheduler.plugins.base_plugin import (BasePlugin, PluginStatus,
                                                   StatusCode)
from skyflow.templates import Cluster, Job
from skyflow.templates.resource_template import AcceleratorEnum, ResourceEnum


def is_subset_and_values_smaller(dict1: dict, dict2: dict) -> bool:
    """Determines if all values in dict2 are smaller than corresponding values in dict1."""
    # Check if all keys in dict2 are in dict1
    if all(key in dict1 for key in dict2):
        # Check if all values in dict2 are smaller than corresponding values in dict1
        return all(dict2[key] <= dict1[key] for key in dict2)
    return False


class DefaultPlugin(BasePlugin):
    """DefaultPlugin implements the `filter` and `score` methods."""

    def filter(self, cluster: Cluster, job: Job) -> PluginStatus:
        print("in default plugin filter")
        import pdb;pdb.set_trace()
        """This filter plugin checks if the cluster has sufficient capacity."""
        job_resuources = job.spec.resources
        cluster_resources = cluster.status.allocatable_capacity
        for node_resources in cluster_resources.values():
            if is_subset_and_values_smaller(node_resources, job_resuources):
                return PluginStatus(code=StatusCode.SUCCESS,
                                    message="Sufficient capacity.")
        return PluginStatus(code=StatusCode.UNSCHEDULABLE,
                            message="Insufficient capacity.")

    def score(self, cluster: Cluster, _) -> Tuple[float, PluginStatus]:
        """Returns a score based on the dot product between cluster and job resources.

        The scoring function is simple; which cluster has the highest score: CPUs + 10 * GPUs.
        """
        score: float = 0
        cluster_resources = cluster.status.allocatable_capacity
        acc_types = [a.value for a in AcceleratorEnum]
        for node_resources in cluster_resources.values():
            for resource_type, resource_count in node_resources.items():
                if resource_type == ResourceEnum.CPU.value:
                    score += resource_count
                elif resource_type == ResourceEnum.GPU.value:
                    score += 10 * resource_count
                elif resource_type in acc_types:
                    score += 10 * resource_count
        return score, PluginStatus(code=StatusCode.SUCCESS,
                                   message="Score computed.")

    def spread(self, clusters: List[Cluster],
               job: Job) -> Tuple[Dict[str, int], PluginStatus]:
        """Compute the number of replicas that should be placed on each cluster.

        It greedily assigns replicas to clusters based on the available capacity.
        """
        job_replicas = job.spec.replicas
        job_clusters = {}
        job_resource = deepcopy(job.spec.resources)

        print(job_resource)
        # Greedily assign clusters replicas.
        total_cluster_replicas = 0
        print("***CLUSTERS***")
        print(clusters)
        for cluster_obj in clusters:  # pylint: disable=too-many-nested-blocks
            cluster_replicas = 0
            alloc_capacity = deepcopy(cluster_obj.status.allocatable_capacity)
            print(alloc_capacity)
            # Predict how many replicas can fit onto each node for each cluster.
            for _, node_resource in alloc_capacity.items():
                while True:
                    if total_cluster_replicas == job_replicas:
                        break
                    if is_subset_and_values_smaller(node_resource,
                                                    job_resource):
                        for resource_type in node_resource:
                            if resource_type in job_resource:
                                node_resource[resource_type] -= job_resource[
                                    resource_type]
                        total_cluster_replicas += 1
                        cluster_replicas += 1
                    else:
                        break
            job_clusters[cluster_obj.get_name()] = cluster_replicas
            if total_cluster_replicas == job_replicas:
                break
        print("total replicas=" + str(total_cluster_replicas))
        # Can't schedule job. Returns a null dict.
        if total_cluster_replicas < job_replicas:
            return {}, PluginStatus(code=StatusCode.UNSCHEDULABLE,
                                    message="Insufficient capacity.")

        success = PluginStatus(code=StatusCode.SUCCESS,
                               message="Spread computed.")
        return {k: v for k, v in job_clusters.items() if v > 0}, success
