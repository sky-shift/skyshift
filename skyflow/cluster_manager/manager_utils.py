from skyflow.cluster_manager.kubernetes_manager import KubernetesManager
from skyflow.templates import Cluster


def setup_cluster_manager(cluster_obj: Cluster):
    cluster_type = cluster_obj.spec.manager
    cluster_name = cluster_obj.get_name()

    if cluster_type in ['k8', 'kubernetes']:
        cluster_manager_cls = KubernetesManager
    else:
        raise ValueError(f"Cluster type {cluster_type} not supported.")

    # Get the constructor of the class
    constructor = cluster_manager_cls.__init__
    # Get the parameter names of the constructor
    class_params = constructor.__code__.co_varnames[1:constructor.__code__.
                                                    co_argcount]

    # Filter the dictionary keys based on parameter names
    args = {
        k: v
        for k, v in dict(cluster_obj.metadata).items() if k in class_params
    }
    # Create an instance of the class with the extracted arguments.
    return cluster_manager_cls(**args)