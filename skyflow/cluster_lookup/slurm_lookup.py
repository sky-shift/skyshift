"""
Lookup Slurm clusters under Kubeconfig.
"""
from typing import Any, List
from skyflow import utils
from skyflow.api_client.cluster_api import ClusterAPI
from skyflow.globals import SLURM_CONFIG_PATH
from skyflow.utils.slurm_utils import *

def lookup_slurm_config(cluster_api: ClusterAPI) -> List[Any]:
    """
    Loads clusters listed under the Kube config file.
        Args:
            cluster_api: cluster api object to interface with api server.
        Returns:
            List of sanitized Slurm cluster names.
    """
    slurm_config = VerifySlurmConfig()
    cluster_contexts = []
    for cluster in cluster_api.list().objects:
        if slurm_config.verify_configuration(cluster.metadata.name):
            cluster_contexts.append(cluster)
        else:
            cluster_api.delete(cluster.metadata.name)        
    return [
        utils.sanitize_cluster_name(context.metadata.name)
        for context in cluster_contexts
    ]
if __name__ == '__main__':
    cluster_api = ClusterAPI()
    print(lookup_slurm_config(cluster_api))
