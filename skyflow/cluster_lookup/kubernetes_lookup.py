"""
Lookup Kuberntes clusters under Kubeconfig.
"""
from typing import List

from kubernetes import config


def lookup_kube_config() -> List[dict]:
    """
    Loads clusters listed under the Kube config file.
    """
    # List all cluster contexts from kubeconfig
    try:
        contexts, _ = config.list_kube_config_contexts(
            config_file='~/.kube/config')
    except config.config_exception.ConfigException as error:
        error_msg = str(error)
        # Invalid Kubeconfig file.
        if 'current-context' in error_msg:
            raise ValueError(
                'Invalid kubeconfig file. Set `current-context` in your '
                'kube-config file by running `kubectl config use-context [NAME]`.'
            ) from error
        raise error
    return [context["name"] for context in contexts]
