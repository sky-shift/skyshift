"""
Lookup Ray clusters under skyconf.
"""
import logging
import os
from typing import Any, List, Tuple, Union

import yaml

from skyflow import utils
from skyflow.api_client.cluster_api import ClusterAPI
from skyflow.globals import RAY_CLUSTERS_CONFIG_PATH
from skyflow.utils.utils import fetch_absolute_path, handle_invalid_config

logging.basicConfig(
    level=logging.INFO,
    format="%(name)s - %(asctime)s - %(levelname)s - %(message)s")

@handle_invalid_config
def _load_sky_config(file_path: str) -> dict:
    """
    Attempt to load sky config from a specified file.
    Returns the config dictionary.
    """
    expanded_path = fetch_absolute_path(file_path)
    if not os.path.exists(expanded_path):
        return {}
    with open(expanded_path, 'r') as file:
        return yaml.safe_load(file)

def add_cluster_to_config(cluster_name: str, host: str, user: str, ssh_key: str, password: str):
    """
    Add a new Ray cluster configuration to the .skyconf/ray.yaml file.
    """
    config_path = os.path.expanduser(RAY_CLUSTERS_CONFIG_PATH)
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    config = _load_sky_config(config_path) or {}

    clusters = config.get('clusters', {})
    clusters[cluster_name] = {
        'host': host,
        'username': user,
        'ssh_key': ssh_key,
        'password': password
    }
    config['clusters'] = clusters

    with open(config_path, 'w') as file:
        yaml.safe_dump(config, file)

def lookup_ray_config(cluster_api: ClusterAPI) -> List[Any]:
    """
    Process all clusters to find their sky config details.
    """
    processed_configs = []

    # Process default sky config path first
    config = _load_sky_config(RAY_CLUSTERS_CONFIG_PATH)
    if config:
        processed_configs.append(config)

    # Process each cluster's specified config
    existing_clusters = [cluster.metadata.name for cluster in cluster_api.list().objects]
    cluster_dictionaries = []
    for config in processed_configs:
        clusters_info = config.get('clusters', {})
        for cluster_name, access_info in clusters_info.items():
            if cluster_name in existing_clusters:
                continue
            cluster_dict = {
                "kind": "Cluster",
                "metadata": {
                    "name": cluster_name,
                },
                "spec": {
                    "manager": "ray",
                    "username": access_info.get('username', None),
                    "host": access_info.get('host', None),
                    "config_path": access_info.get('config_path', RAY_CLUSTERS_CONFIG_PATH),
                    "ssh_key_path": access_info.get('ssh_key', None),
                    "password": access_info.get('password', None),
                },
            }
            cluster_dictionaries.append(cluster_dict)
    return cluster_dictionaries


#if __name__ == "__main__":
#    cluster_api = ClusterAPI()
#    access_info = lookup_ray_config(cluster_api)
#    print("Processed access information:", access_info)
#    cluster_obj = ClusterAPI().create(config=access_info[0])
#    print("Created cluster object:", cluster_obj)