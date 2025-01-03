"""
Lookup Kuberntes clusters under Kubeconfig.
"""
from typing import Any, List, Tuple

from kubernetes import config

from skyshift.api_client.cluster_api import ClusterAPI
from skyshift.globals import K8_MANAGERS, KUBE_CONFIG_DEFAULT_PATH
from skyshift.utils.utils import sanitize_cluster_name


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
    existing_configs = {KUBE_CONFIG_DEFAULT_PATH}
    cluster_list = cluster_api.list().objects
    for cluster in cluster_list:
        if cluster.spec.manager in K8_MANAGERS:
            if cluster.spec.config_path:
                existing_configs.add(cluster.spec.config_path)

    context_to_config = {}
    for cfg in existing_configs:
        contexts, success = _load_kube_config_contexts(cfg)
        if success:
            for context in contexts:
                context_to_config[sanitize_cluster_name(context['name'])] = cfg

    existing_clusters_names = context_to_config.keys()

    existing_clusters_api = [cluster.metadata.name for cluster in cluster_list]

    clusters = []

    for cluster_name in existing_clusters_names:
        if cluster_name in existing_clusters_api:
            continue

        cluster_dictionary = {
            "kind": "Cluster",
            "metadata": {
                "name": cluster_name,
            },
            "spec": {
                "manager": "k8",
                "config_path": context_to_config[cluster_name],
            },
        }
        clusters.append(cluster_dictionary)

    return clusters
