from typing import List
from kubernetes import client, config


def lookup_kube_config() -> List[dict]:
    # Load kubeconfig file
    config.load_kube_config()

    # Initialize clients
    v1 = client.CoreV1Api()
    config_v1 = client.Configuration()

    # List all cluster contexts from kubeconfig
    contexts, _ = config.list_kube_config_contexts()
    kubernetes_dicts = []
    for context in contexts:
        context_name = context['name']
        namespace_name = context['context']['namespace']
        kubernetes_dicts.append({
            'kind': 'Cluster',
            'metadata': {
                'name': context_name,
                'namespace': namespace_name,
            },
            'spec': {
                'manager': 'k8',
            }
        })
    return kubernetes_dicts