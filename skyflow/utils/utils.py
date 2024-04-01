"""
Utility functions for Skyflow.
"""
import importlib
import json
import os
import shutil
from typing import Dict, List, Optional, Union

import requests
import yaml
from skyflow.utils.utils_exception import InvalidClusterNameError, ObjectLoadingError


API_SERVER_CONFIG_PATH = "~/.skyconf/config.yaml"

OBJECT_TEMPLATES = importlib.import_module("skyflow.templates")


def sanitize_cluster_name(value: str) -> str:
    """
    Validates the name field of a Cluster, ensuring
    it does not contain whitespaces, @ or '/'.
    """
    if not value or value.isspace() or len(value) == 0:
        raise InvalidClusterNameError(f"Name format is invalid: {value}")
    sanitized_value = value.replace(" ", "-space-").replace("/",
                                                            "-dash-").replace(
                                                                "@", "-at-")
    return sanitized_value


def generate_manager_config(host: str, port: int):
    """Generates the API server config file."""
    absolute_path = os.path.expanduser(API_SERVER_CONFIG_PATH)
    # If path exists, check if host and port are identical
    if os.path.exists(absolute_path):
        with open(absolute_path, "r") as config_file:
            config_dict = yaml.safe_load(config_file)

            if (config_dict["api_server"]["host"] == host
                    and config_dict["api_server"]["port"] == port
                    and "secret" in config_dict["api_server"]):
                print("API server config already exists. Skipping generation.")
                return

    config_dict = {
        "api_server": {
            "host": host,
            "port": port,
            "secret": os.urandom(256).hex(),
        },
        "users": [],
    }
    os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
    with open(absolute_path, "w") as config_file:
        yaml.dump(config_dict, config_file)


def load_object(response: Union[Dict, List[Dict]]):
    """
    Loads an object or a list of objects (from templates) from a dictionary.
    """
    if isinstance(response, list):
        return [load_single_object(item) for item in response]
    return load_single_object(response)


def load_single_object(item: dict):
    """
    Loads a single object (from templates) from a dictionary.
    """
    try:
        kind = item["kind"]
        object_class = getattr(OBJECT_TEMPLATES, kind)
        if object_class:
            return object_class(**item)
        raise ObjectLoadingError(f"Unknown kind: {kind}")
    except KeyError as error:
        raise ObjectLoadingError(f"Missing expected key: {error}")


def watch_events(url: str, headers: Optional[dict] = None):
    """Yields watch events from the given URL."""
    if headers:
        response = requests.get(url, stream=True, headers=headers)
    else:
        response = requests.get(url, stream=True)
    for line in response.iter_lines():
        if line:
            data = json.loads(line.decode("utf-8"))
            yield data


def match_labels(labels: dict, labels_selector: dict):
    """Returns True if the labels match the label selector."""
    if not labels_selector:
        return True
    for key, value in labels_selector.items():
        if key not in labels or labels[key] != value:
            return False
    return True


def load_manager_config():
    """Loads the API server config file."""
    try:
        with open(os.path.expanduser(API_SERVER_CONFIG_PATH),
                  "r") as config_file:
            config_dict = yaml.safe_load(config_file)
    except FileNotFoundError as error:
        raise Exception(
            f"API server config file not found at {API_SERVER_CONFIG_PATH}."
        ) from error
    return config_dict


def delete_unused_cluster_config(cluster_name: str):
    """Deletes the cluster config directory from the Skyconf directory."""
    shutil.rmtree(f"{os.path.expanduser('~/.skyconf')}/{cluster_name}")
