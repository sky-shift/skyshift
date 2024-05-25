"""
Lookup Slurm clusters under Kubeconfig.
"""
import traceback
from typing import Any, List

from skyflow import utils
from skyflow.api_client.cluster_api import ClusterAPI
from skyflow.cluster_manager.slurm import SlurmConfig
from skyflow.globals import SLURM_CONFIG_DEFAULT_PATH, SLURM_MANAGERS


def _safe_load_slurm_config(config_path: str) -> dict:
    try:
        slurm_config = SlurmConfig(config_path=config_path)
    except Exception as error:
        print(traceback.format_exc())
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
    existing_configs = [SLURM_CONFIG_DEFAULT_PATH]
    existing_contexts = []
    slurm_config = _safe_load_slurm_config(SLURM_CONFIG_DEFAULT_PATH)
    if slurm_config:
        existing_contexts.extend(slurm_config.clusters)
    
    for cluster in cluster_api.list().objects:
        if cluster.spec.manager not in SLURM_MANAGERS:
            continue
        
        path = cluster.spec.config_path if cluster.spec.config_path else SLURM_CONFIG_DEFAULT_PATH
        if path not in existing_configs:
            gen_config = _safe_load_slurm_config(path)
            if gen_config:
                existing_contexts.extend(gen_config.clusters)
                existing_configs.append(path)
        else:
            cluster_api.delete(cluster.metadata.name)        
    return [utils.sanitize_cluster_name(context) for context in existing_contexts ]

