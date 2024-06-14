"""
Specifies the default scheduler plugin for the SchedulerController.
"""
from copy import deepcopy
from typing import Dict, List, Tuple

from skyflow.scheduler.plugins import plugin_utils as utils
from skyflow.scheduler.plugins.base_plugin import (BasePlugin, PluginStatus,
                                                   StatusCode)
from skyflow.templates import Cluster, Job
from skyflow.templates.job_template import (DEFAULT_MAX_WEIGHT,
                                            DEFAULT_MIN_WEIGHT, PreferenceSpec)
from skyflow.templates.resource_template import AcceleratorEnum, ResourceEnum


def check_gpu_requirements(job: dict, cluster: dict) -> bool:
    """
    Checks if the total number of GPUs required by the job is greater than the total
    number of GPUs available in the cluster.
    """
    total_gpus = sum(cluster.get(gpu.name, 0) for gpu in AcceleratorEnum)
    return job[ResourceEnum.GPU.value] > total_gpus


def is_subset_and_values_smaller(dict1: dict, dict2: dict) -> bool:
    """
    Determines if all values in dict2 are smaller than corresponding values in dict1,
    ignoring keys with value 0 in dict2. Also handles GPU requirements by checking total
    available GPUs if any GPU is requested.
    """
    filtered_dict2 = {key: value for key, value in dict2.items() if value != 0}

    if ResourceEnum.GPU.value in filtered_dict2 and check_gpu_requirements(
            filtered_dict2, dict1):
        filtered_dict2.pop(ResourceEnum.GPU.value)

    # Check remaining resources
    if all(key in dict1 for key in filtered_dict2):
        return all(filtered_dict2[key] <= dict1[key] for key in filtered_dict2)
    return False


def preference_evaluation_satisfied(cluster: Cluster,
                                    preference: PreferenceSpec) -> bool:
    """
    Checks to ensure each criteria of a preference stanza is met. This
    is an AND operation of all criteria operations (match_labels and
    match_expressions). Note: implementations of criteria operations
    are independent of this AND operation. An example below shows
    cluster must have a label with "purpose": "dev" AND
    "function": "performance-testing" AND
    "location": "us-south" OR "location": "us-south"
        preferences: [{ name: preferences-1,
            match_labels: {
                {purpose: dev},
                {function: performance-testing},
            },
            match_expressions: [{
                key: location,
                operator: In,
                values: us-south, us-west
            }],
            weight: 100.0
        }]
    """
    cluster_labels = cluster.metadata.labels
    # Determine if 'match_labels' criteria met
    is_match_label_satisfied = utils.match_labels_satisfied(
        preference.match_labels, cluster_labels)
    if not is_match_label_satisfied:
        return False

    # Determine if each 'match_expressions' criteria is met
    for expression in preference.match_expressions:
        is_ok, _ = utils.match_expressions_satisfied(expression,
                                                     cluster_labels)
        if not is_ok:
            return False
    return True


def get_cluster_preference_weight(cluster: Cluster, job: Job) -> float:
    """
    Loops through each preference of the placement stanza
    to determine if the cluster meets the preference
    criteria. If the criteria is satisfied the preference
    weight is retreived as a local weighted preference.
    If multiple preferences are satisfied then the highest
    weighted preference is selected as the final local
    weighted preference.  If no matching preference
    criteria is found, the cluster is assigned the
    lowest possible weight (DEFAULT_MIN_WEIGHT).  Finally
    the local weighted preference is normalized against
    the DEFAULT_MAX_WEIGHT and returns a value between
    DEFAULT_MIN_WEIGHT - DEFAULT_MAX_WEIGHT.
    """
    # Check for job placement preferences
    placement = job.spec.placement

    # Default weight
    local_preference_weight: float = DEFAULT_MIN_WEIGHT

    # Highest weight
    global_highest_weight = local_preference_weight

    # Process job placement stanza
    if placement:
        # Check for job preferences
        preferences = placement.preferences
        if preferences:
            # Check each preference stanza in isolation ('OR' Condition)
            for preference in preferences:

                # Check for global highest weight (irrespective of
                # of a preference match)
                if preference.weight > global_highest_weight:
                    global_highest_weight = preference.weight

                # If a preference match is found and the preferernce
                # weight is higher than the local preference weight,
                # then save preference weight as the new local
                # preference weight.
                preference_match = preference_evaluation_satisfied(
                    cluster, preference)
                if preference_match and preference.weight > local_preference_weight:
                    local_preference_weight = preference.weight

    # Normalize local preference weight for provided cluster
    normalized_wt = local_preference_weight * DEFAULT_MAX_WEIGHT / global_highest_weight
    return normalized_wt


class DefaultPlugin(BasePlugin):
    """DefaultPlugin implements the `filter` and `score` methods."""

    def filter(self, cluster: Cluster, job: Job) -> PluginStatus:
        """This filter plugin checks if the cluster has sufficient capacity."""
        job_resuources = job.spec.resources
        cluster_resources = cluster.status.allocatable_capacity
        for node_resources in cluster_resources.values():
            if is_subset_and_values_smaller(node_resources, job_resuources):
                return PluginStatus(code=StatusCode.SUCCESS,
                                    message="Sufficient capacity.")
        return PluginStatus(code=StatusCode.UNSCHEDULABLE,
                            message="Insufficient capacity.")

    def score(self, cluster: Cluster, job: Job) -> Tuple[float, PluginStatus]:
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
        preference_weight = get_cluster_preference_weight(cluster, job)
        final_score = score * preference_weight
        return final_score, PluginStatus(code=StatusCode.SUCCESS,
                                         message="Score computed.")

    def spread(self, clusters: List[Cluster],
               job: Job) -> Tuple[Dict[str, int], PluginStatus]:
        """Compute the number of replicas that should be placed on each cluster.

        It greedily assigns replicas to clusters based on the available capacity.
        """
        job_replicas = job.spec.replicas
        job_clusters = {}
        job_resource = deepcopy(job.spec.resources)

        # Greedily assign clusters replicas.
        total_cluster_replicas = 0

        for cluster_obj in clusters:  # pylint: disable=too-many-nested-blocks
            cluster_replicas = 0
            alloc_capacity = deepcopy(cluster_obj.status.allocatable_capacity)
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
        # Can't schedule job. Returns a null dict.
        if total_cluster_replicas < job_replicas:
            return {}, PluginStatus(code=StatusCode.UNSCHEDULABLE,
                                    message="Insufficient capacity.")

        success = PluginStatus(code=StatusCode.SUCCESS,
                               message="Spread computed.")
        return {k: v for k, v in job_clusters.items() if v > 0}, success
