"""
Lookup Kuberntes clusters under Kubeconfig.
"""
import os
from typing import Any, List, Tuple

from kubernetes import config

from skyflow import utils
from skyflow.api_client.cluster_api import ClusterAPI
from skyflow.globals import KUBE_CONFIG_DEFAULT_PATH, K8_MANAGERS


def _fetch_absolute_path(path: str) -> str:
    """
    Fetches the absolute path of a given path.
    """
    return os.path.abspath(os.path.expanduser(path))


def _load_kube_config_contexts(file_path: str) -> Tuple[List[Any], bool]:
    """
    Attempt to load kube config contexts from a specified file.
    Returns a tuple of the contexts list and a boolean indicating success or failure.
    """
    try:
        contexts, _ = config.list_kube_config_contexts(config_file=file_path)
        return contexts, True
    except config.config_exception.ConfigException as error:
        _handle_invalid_config(file_path, str(error))
        return [], False


def _handle_invalid_config(file_path: str, error_msg: str):
    """
    Prints an appropriate message based on the error encountered.
    """
    print(error_msg)
    if 'current-context' in error_msg:
        print(f'Invalid kubeconfig file {file_path}. Skipping this. '
              'Set `current-context` in your kube-config file '
              'by running `kubectl config use-context [NAME]`.')
    elif 'Invalid kube-config file' in error_msg:
        print(f'Invalid kubeconfig file {file_path}. Skipping this. '
              'Ensure the kubeconfig file is valid.')


def lookup_kube_config(cluster_api: ClusterAPI) -> List[Any]:
    """
    Process all clusters to find their kube config contexts.
    """
    existing_configs = [KUBE_CONFIG_DEFAULT_PATH]
    existing_contexts = []

    # Process default KUBE config path first
    contexts, success = _load_kube_config_contexts(KUBE_CONFIG_DEFAULT_PATH)
    if success:
        existing_contexts.extend(contexts)

    # Process each cluster's specified config
    for cluster in cluster_api.list().objects:
        if cluster.spec.manager not in K8_MANAGERS:
            continue
        path = cluster.spec.config_path if cluster.spec.config_path else '~/.kube/config'
        path = _fetch_absolute_path(path)

        if path not in existing_configs:
            contexts, success = _load_kube_config_contexts(path)
            if success:
                existing_contexts.extend(contexts)
                existing_configs.append(path)
            else:
                cluster_api.delete(cluster.metadata.name)

    return [
        utils.sanitize_cluster_name(context["name"])
        for context in existing_contexts
    ]
