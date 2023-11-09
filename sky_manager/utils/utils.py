import importlib
import json
import os

import requests
import yaml

from sky_manager.cluster_manager.kubernetes_manager import KubernetesManager
from sky_manager.templates import Cluster

API_SERVER_CONFIG_PATH = '~/.skym/config.yaml'

def generate_object(response: dict):
    object_templates = importlib.import_module('sky_manager.templates')
    kind = response['kind']
    object_class = getattr(object_templates, kind)
    return object_class.from_dict(response)

def watch_events(url: str):
    response = requests.get(url, stream=True)
    for line in response.iter_lines():
        if line:
            data = json.loads(line.decode('utf-8'))
            yield data

def setup_cluster_manager(cluster_obj: Cluster):
    cluster_type = cluster_obj.spec.manager
    cluster_name = cluster_obj.meta.name

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
        for k, v in dict(cluster_obj.meta).items() if k in class_params
    }
    # Create an instance of the class with the extracted arguments.
    return cluster_manager_cls(**args)

def generate_manager_config(host: str, port: int):
    """Generates the API server config file."""
    config_dict = {
        'api_server': {
            'host': host,
            'port': port,
        },
    }
    absolute_path = os.path.expanduser(API_SERVER_CONFIG_PATH)
    os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
    with open(absolute_path, 'w') as config_file:
        yaml.dump(config_dict, config_file)


def load_manager_config():
    """Loads the API server config file."""
    try:
        with open(os.path.expanduser(API_SERVER_CONFIG_PATH),
                  'r') as config_file:
            config_dict = yaml.safe_load(config_file)
        host = config_dict['api_server']['host']
        port = config_dict['api_server']['port']
    except FileNotFoundError as e:
        raise Exception(
            f'API server config file not found at {API_SERVER_CONFIG_PATH}.')
    except KeyError as e:
        raise Exception(
            f'API server config file at {API_SERVER_CONFIG_PATH} is invalid.')
    return host, port