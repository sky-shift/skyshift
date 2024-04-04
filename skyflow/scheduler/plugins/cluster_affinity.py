"""
ClusterAffinity plugin implements the `filter` plugin.

The `filter` plugin checks for clusters that the job is not allowed to be scheduled on.
"""
from skyflow.api_client import FilterPolicyAPI
from skyflow.scheduler.plugins.base_plugin import (BasePlugin, PluginStatus,
                                                   StatusCode)
from skyflow.templates import Cluster, Job


class ClusterAffinityPlugin(BasePlugin):
    """Prevents jobs from being scheduled on clusters that do not satisfy the job's affinity."""

    def filter(self, cluster: Cluster, job: Job) -> PluginStatus:
        # Filter for clusters.
        filter_policy_api = FilterPolicyAPI(namespace=job.get_namespace())
        all_policies = filter_policy_api.list()

        # Find filter policies that have labels that are a subset of the job's labels.
        filter_policies = []
        for f_policy in all_policies.objects:
            fp_dict_labels = f_policy.spec.labels_selector
            job_labels = job.metadata.labels
            is_subset = False
            if fp_dict_labels:
                is_subset = all(k in job_labels and job_labels[k] == v
                                for k, v in fp_dict_labels.items())
            if is_subset:
                filter_policies.append(f_policy)

        if not filter_policies:
            return PluginStatus(code=StatusCode.SUCCESS,
                                message="No filter policies found.")

        # Filter for clusters that satisfy the filter policies.
        c_name = cluster.get_name()
        for f_policy in filter_policies:
            include_list = f_policy.spec.cluster_filter.include
            exclude_list = f_policy.spec.cluster_filter.exclude
            if c_name not in include_list:
                return PluginStatus(code=StatusCode.UNSCHEDULABLE,
                                    message="Cluster not in include list.")

            if c_name in exclude_list:
                return PluginStatus(code=StatusCode.UNSCHEDULABLE,
                                    message="Cluster in exclude list.")
        return PluginStatus(code=StatusCode.SUCCESS,
                            message="Cluster satisfies filter policies.")
