"""
Utility functions for SkyShift.
"""
import importlib
import json
import logging
import os
import re
import shutil
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Union

import requests
import yaml
from rapidfuzz import process

from skyflow.globals import (ACCELERATOR_KEYWORDS, API_SERVER_CONFIG_PATH,
                             SKYCONF_DIR)
from skyflow.templates.resource_template import AcceleratorEnum, ResourceEnum

OBJECT_TEMPLATES = importlib.import_module("skyflow.templates")


def parse_resource_cpu(resource_str):
    """Parse CPU string to cpu count."""
    unit_map = {"m": 1e-3, "K": 1e3}
    value = re.search(r"\d+", resource_str).group()
    unit = resource_str[len(value):]
    return float(value) * unit_map.get(unit, 1)


def parse_resource_memory(resource_str):
    """Parse resource string to megabytes."""
    unit_map = {"Ki": 2**10, "Mi": 2**20, "Gi": 2**30, "Ti": 2**40}
    value = re.search(r"\d+", resource_str).group()
    unit = resource_str[len(value):]
    return float(value) * unit_map.get(unit, 1) / (2**20)


def format_resource_units(value: float) -> str:
    """
    Converts a given value to the most optimal units (PB, TB, GB, MB).
    """
    units = ['PB', 'TB', 'GB']
    thresholds = [1 << 30, 1 << 20, 1 << 10]
    for unit, threshold in zip(units, thresholds):
        if value >= threshold:
            return f"{value / threshold:.2f} {unit}"
    return f"{value} MB"


def is_accelerator_label(label: str, threshold: int = 80) -> bool:
    """Uses fuzzy matching to determine if a label is an accelerator label."""
    _, score, _ = process.extractOne(label, ACCELERATOR_KEYWORDS)
    return score >= threshold


def sanitize_cluster_name(value: str) -> str:
    """
    Validates the name field of a Cluster, ensuring
    it does not contain whitespaces, @, _ or '/'.
    """
    if not value or value.isspace() or len(value) == 0:
        raise ValueError(f"Name format is invalid: {value}")
    sanitized_value = value.replace(" ", "-space-").replace(
        "/", "-dash-").replace("@", "-at-").replace("_", "-underscore-")
    return sanitized_value


def fetch_absolute_path(path: str) -> str:
    """
    Fetches the absolute path of a given path.
    """
    return os.path.abspath(os.path.expanduser(path))


def handle_invalid_config(func):
    """
    Decorator to handle invalid configuration files.
    """

    def wrapper(file_path: str) -> Optional[Tuple[Union[dict, None], bool]]:
        config = None
        try:
            config = func(file_path)
            return config
        except (yaml.YAMLError, FileNotFoundError):
            logger = logging.getLogger(__name__)
            _handle_invalid_file(file_path, logger)
            return None

    return wrapper


def _handle_invalid_file(file_path: str, logger: logging.Logger):
    """
    Prints an appropriate message based on the error encountered.
    """
    logger.error(f'Invalid file {file_path}. Skipping this. '
                 'Ensure the file is valid and accessible.')


def unsanitize_cluster_name(value: Optional[str]) -> str:
    """
    Reverts the sanitized cluster name back to the original name.
    """
    if value is None:
        return ""
    return value.replace("-space-", " ").replace("-dash-", "/").replace(
        "-at-", "@").replace("-underscore-", "_")


def generate_manager_config(host: str, port: int):
    """Generates the API server config file."""
    absolute_path = os.path.expanduser(API_SERVER_CONFIG_PATH)

    if host == '0.0.0.0':
        # Fetch public IP address of the machine.
        response = requests.get('https://api.ipify.org?format=json')
        host = response.json()['ip']

    # If path exists, check if host and port are identical
    if os.path.exists(absolute_path):
        with open(absolute_path, "r") as config_file:
            config_dict = yaml.safe_load(config_file)

            if (config_dict["api_server"]["host"] == host
                    and config_dict["api_server"]["port"] == port
                    and "secret" in config_dict["api_server"]):
                if ("contexts" in config_dict and "users" in config_dict
                        and "current_context" in config_dict):
                    print(
                        "API server config already exists. Skipping generation."
                    )
                    return

    config_dict = {
        "api_server": {
            "host": host,
            "port": port,
            "secret": os.urandom(256).hex(),
        },
        "current_context": "",
        "contexts": [],
        "users": [],
    }
    os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
    with open(absolute_path, "w") as config_file:
        yaml.dump(config_dict, config_file)


def generate_temp_directory(directory_path):
    """
    Generates temporary directorys in SKYCONF for system use.
    """
    absolute_path = os.path.expanduser(SKYCONF_DIR + directory_path)
    if os.path.exists(absolute_path + directory_path):
        return
    os.makedirs(os.path.dirname(absolute_path), exist_ok=True)


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


def watch_events(url: str, headers: Optional[dict] = None):
    """Yields watch events from the given URL."""
    with requests.get(url, stream=True, headers=headers) as response:
        try:
            for line in response.iter_lines():
                if line:  # Make sure the line is not empty
                    data = json.loads(line.decode("utf-8"))
                    yield data
        finally:
            response.close()


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


def fetch_datetime():
    """Returns the current date and time as a string."""
    # Get the current datetime in UTC
    current_time = datetime.now(timezone.utc).replace(tzinfo=None)
    # Format the datetime as a string in ISO 8601 format
    return current_time.isoformat(timespec='seconds')


def compute_datetime_delta(start: str, end: str):
    """Computes the difference between two datetimes and returns a formatted string."""
    start_time = datetime.fromisoformat(start)
    end_time = datetime.fromisoformat(end)
    # Calculate the difference between the two times
    delta = end_time - start_time
    days = delta.days
    seconds = delta.seconds

    # Calculate hours, minutes, and seconds
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    # Format the output based on the largest non-zero value.
    if days > 0:
        return f"{days}d"
    if hours > 0:
        return f"{hours}h"
    if minutes > 0:
        return f"{minutes}m"
    return f"{seconds}s"


def update_manager_config(config: dict):
    """Updates the API server config file."""
    with open(os.path.expanduser(API_SERVER_CONFIG_PATH), "w") as config_file:
        yaml.dump(config, config_file)


def fuzzy_map_gpu(
    resources_dict: Dict[str, Dict[str,
                                   float]]) -> Dict[str, Dict[str, float]]:
    """
    Maps GPUs to the closest match in the enum class using rapidfuzz.
    """
    enum_values = [e.value for e in AcceleratorEnum]
    non_gpu_keys = {e.value for e in ResourceEnum}

    for _, resources in resources_dict.items():
        for key in list(resources.keys()):
            if key not in non_gpu_keys:
                closest_match = process.extractOne(key, enum_values)
                if closest_match:
                    resources[closest_match[0]] = resources.pop(key)
    return resources_dict
