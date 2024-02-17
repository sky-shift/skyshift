"""
Lookup Kuberntes clusters under Kubeconfig.
"""
from typing import List

from kubernetes import config


def lookup_kube_config() -> List[dict]:
    """
    Loads clusters listed under the Kube config file.
    """
    # Load kubeconfig file
    config.load_kube_config()

    # List all cluster contexts from kubeconfig
    contexts, _ = config.list_kube_config_contexts()
    return [context["name"] for context in contexts]
