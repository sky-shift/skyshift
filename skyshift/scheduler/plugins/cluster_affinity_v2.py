"""
ClusterAffinityV2 plugin implements the `filter` plugin for advanced filtering.

The `filter` plugin checks for clusters that the job is not allowed to be scheduled on.
"""
from skyshift.scheduler.plugins import plugin_utils as utils
from skyshift.scheduler.plugins.base_plugin import (BasePlugin, PluginStatus,
                                                    StatusCode)
from skyshift.templates import Cluster, Job
from skyshift.templates.job_template import FilterSpec


# Check all criteria of one filter stanza
def _filter_satisfied(cluster: Cluster, fltr: FilterSpec) -> bool:
    """
    Checks to ensure each criteria of a filter stanza is met. This is
    an AND operation of all criteria operations (match_labels and
    match_expressions). Note: implementations of criteria operations
    are independent of this AND operation. An example below shows
    cluster must have a label with "purpose": "dev" AND
    "function": "performance-testing" AND
    "location": "us-south" OR "location": "us-south"
        filters: [{ name: filter-1,
            match_labels: {
                {purpose: dev},
                {function: performance-testing},
            },
            match_expressions: [{
                key: location,
                operator: In,
                values: us-south, us-west
            }]
        }]
    """
    cluster_labels = cluster.metadata.labels
    # Determine if 'match_labels' criteria met
    match_labels_satisfied = utils.match_labels_satisfied(
        fltr.match_labels, cluster_labels)
    if not match_labels_satisfied:
        return False

    # Determine if each 'match_expressions' criteria is met
    for expression in fltr.match_expressions:
        is_ok, _ = utils.match_expressions_satisfied(expression,
                                                     cluster_labels)
        if not is_ok:
            return False
    return True


class ClusterAffinityPluginV2(BasePlugin):
    """Prevents jobs from being scheduled on clusters that do not satisfy the job's affinity."""

    def filter(self, cluster: Cluster, job: Job) -> PluginStatus:
        # Check for job placement restrictions
        placement = job.spec.placement
        if not placement:
            return PluginStatus(code=StatusCode.SUCCESS,
                                message="No placement policies found.")

        # Check for job filters
        filters = placement.filters
        if not filters:
            return PluginStatus(code=StatusCode.SUCCESS,
                                message="No filter policies found.")

        cluster_name = cluster.get_name()
        # Check each filter stanza in isolation ('OR' Condition)
        for fltr in filters:
            filter_satisfied = _filter_satisfied(cluster, fltr)
            if filter_satisfied:
                cluster_name = cluster.get_name()
                return PluginStatus(
                    code=StatusCode.SUCCESS,
                    message=
                    f"Cluster '{cluster_name}' satisfies filter policies.")
        # Failed to find any schedulable filter
        return PluginStatus(
            code=StatusCode.UNSCHEDULABLE,
            message=
            f"Cluster  '{cluster_name}' does not satisfy filter restrictions.")
