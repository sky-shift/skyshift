import importlib
import json
import os

import requests
import yaml

API_SERVER_CONFIG_PATH = '~/.skyconf/config.yaml'

OBJECT_TEMPLATES = importlib.import_module('skyflow.templates')


def load_object(response: dict):
    kind = response['kind']
    object_class = getattr(OBJECT_TEMPLATES, kind)
    return object_class(**response)


def watch_events(url: str):
    response = requests.get(url, stream=True)
    for line in response.iter_lines():
        if line:
            data = json.loads(line.decode('utf-8'))
            yield data


def match_labels(labels: dict, labels_selector: dict):
    """Returns True if the labels match the label selector."""
    if not labels_selector:
        return True
    for k, v in labels_selector.items():
        if k not in labels or labels[k] != v:
            return False
    return True


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
