"""
Lookup Kuberntes clusters under Kubeconfig.
"""
import os
from typing import Any, List

from kubernetes import config

from skyflow import utils
from skyflow.api_client.cluster_api import ClusterAPI


def _fetch_absolute_path(path: str) -> str:
    """
    Fetches the absolute path of a given path.
    """
    return os.path.abspath(os.path.expanduser(path))


def lookup_kube_config(cluster_api: ClusterAPI) -> List[Any]:
    """
    Loads clusters listed under Kube config file(s).
    """
    # List all cluster contexts from kubeconfig and fetch all existing Kubernetes configs.
    existing_configs = []
    existing_contexts = []

    for cluster in cluster_api.list().objects:
        path = cluster.spec.config_path
        if not path:
            path = '~/.kube/config'
        path = _fetch_absolute_path(cluster.spec.config_path)
        if path in existing_configs:
            continue
        try:
            contexts, _ = config.list_kube_config_contexts(config_file=path)
        except config.config_exception.ConfigException as error:
            error_msg = str(error)
            print(error_msg)
            # Invalid Kubeconfig file.
            if 'current-context' in error_msg:
                print(f'Invalid kubeconfig file {path}. Skipping this. '
                      'Set `current-context` in your kube-config file '
                      'by running `kubectl config use-context [NAME]`.')
            elif 'Invalid kube-config file' in error_msg:
                print(f'Invalid kubeconfig file {path}. Skipping this. '
                      'Ensure the kubeconfig file is valid.')
            cluster_api.delete(cluster.metadata.name)
            continue
        existing_contexts.extend(contexts)
        existing_configs.append(path)
    return [
        utils.sanitize_cluster_name(context["name"])
        for context in existing_contexts
    ]
