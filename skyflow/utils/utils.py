"""
Utility functions for Skyflow.
"""
import importlib
import json
import os
from typing import Dict, List, Union

import requests
import yaml

API_SERVER_CONFIG_PATH = "~/.skyconf/config.yaml"

OBJECT_TEMPLATES = importlib.import_module("skyflow.templates")


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
        raise ValueError(f"Unknown kind: {kind}")
    except KeyError as error:
        raise ValueError(f"Missing expected key: {error}") from error


def watch_events(url: str, headers: dict = {}):
    """Yields watch events from the given URL."""
    response = requests.get(url, stream=True, headers=headers)
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
