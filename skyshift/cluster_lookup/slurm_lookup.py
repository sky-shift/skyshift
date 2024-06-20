"""
Lookup Slurm clusters under Kubeconfig.
"""
from typing import Any, List, Optional

from skyshift import utils
from skyshift.api_client.cluster_api import ClusterAPI
from skyshift.cluster_manager.slurm import SlurmConfig
from skyshift.globals import SLURM_CONFIG_DEFAULT_PATH, SLURM_MANAGERS


def _safe_load_slurm_config(config_path: str) -> Optional[SlurmConfig]:
    try:
        slurm_config = SlurmConfig(config_path=config_path)
    except FileNotFoundError:
        print(f"Error loading slurm config: {config_path}")
        return None
    return slurm_config


def lookup_slurm_config(cluster_api: ClusterAPI) -> List[Any]:
    """
    Loads clusters listed under the Kube config file.
        Args:
            cluster_api: cluster api object to interface with api server.
        Returns:
            List of sanitized Slurm cluster names.
    """
    existing_configs = {SLURM_CONFIG_DEFAULT_PATH}
    cluster_list = cluster_api.list().objects
    for cluster in cluster_list:
        if cluster.spec.manager in SLURM_MANAGERS:
            if cluster.spec.config_path:
                existing_configs.add(cluster.spec.config_path)

    context_to_config = {}
    for config in existing_configs:
        slurm_config = _safe_load_slurm_config(config)
        if slurm_config:
            contexts = slurm_config.clusters
            for context in contexts:
                context_to_config[context] = config

    existing_clusters_names: List[str] = [
        utils.sanitize_cluster_name(context) for context in context_to_config
    ]
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
                "manager": "slurm",
                "config_path": context_to_config[cluster_name],
            },
        }
        clusters.append(cluster_dictionary)
    return clusters
