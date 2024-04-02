"""
Lookup Kuberntes clusters under Kubeconfig.
"""
from typing import Any, List

from kubernetes import config

from skyflow import utils
from skyflow.api_client.cluster_api import ClusterAPI


def lookup_kube_config(cluster_api: ClusterAPI) -> List[Any]:
    """
    Loads clusters listed under the Kube config file.
    """
    # List all cluster contexts from kubeconfig
    try:
        contexts, _ = config.list_kube_config_contexts(
            config_file='~/.kube/config')
        for cluster in cluster_api.list().objects:
            try:
                more_contexts, _ = config.list_kube_config_contexts(
                    config_file=cluster.spec.config_path)
                contexts.extend(more_contexts)
            except Exception:  # pylint: disable=broad-except
                # can we just delete here if unable to find/connect via loading kubeconfig?
                cluster_api.delete(cluster.metadata.name)
    except config.config_exception.ConfigException as error:
        error_msg = str(error)
        # Invalid Kubeconfig file.
        if 'current-context' in error_msg:
            raise ValueError(
                'Invalid kubeconfig file. Set `current-context` in your '
                'kube-config file by running `kubectl config use-context [NAME]`.'
            ) from error
        raise error
    return [
        utils.sanitize_cluster_name(context["name"]) for context in contexts
    ]
