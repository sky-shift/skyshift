"""
Lookup Kuberntes clusters under Kubeconfig.
"""
import os
from typing import Any, List, Tuple

from kubernetes import config

from skyflow import utils
from skyflow.api_client.cluster_api import ClusterAPI
from skyflow.globals import KUBE_CONFIG_DEFAULT_PATH


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


#        existing_clusters_names = lookup_kube_config(self.cluster_api)
#        self.logger.info("Found existing clusters: %s.", existing_clusters_names)
#        for cluster_name in existing_clusters_names:
#            self.logger.info("Found existing cluster: %s.", cluster_name)
#            try:
#                cluster_obj = ClusterAPI().get(cluster_name)
#            except APIException:
#                cluster_dictionary = {
#                    "kind": "Cluster",
#                    "metadata": {
#                        "name": cluster_name,
#                    },
#                    "spec": {
#                        "manager": "k8",
#                    },
#                }
#                try:
#                    cluster_obj = ClusterAPI().create(
#                        config=cluster_dictionary)
#                except APIException as error:
#                    self.logger.error(
#                        "Failed to create cluster: %s. Error: %s",
#                        cluster_name, error)
#                    continue


def lookup_kube_config(cluster_api: ClusterAPI) -> List[Any]:
    """
    Process all clusters to find their kube config contexts.
    """
    existing_contexts = []

    # Process default KUBE config path first
    contexts, success = _load_kube_config_contexts(KUBE_CONFIG_DEFAULT_PATH)
    if success:
        existing_contexts.extend(contexts)

    existing_clusters_names = [
        utils.sanitize_cluster_name(context["name"])
        for context in existing_contexts
    ]

    existing_clusters_api = [
        cluster.metadata.name for cluster in cluster_api.list().objects
    ]

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
            },
        }
        clusters.append(cluster_dictionary)

    return clusters
