"""
This module interfaces with the ETCD KV store.

Provides CRUD operations on the ETCD KV store. It is threadsafe
and allows for reads and writes to a range of keys.

Typical usage example:

    >> test_client = ETCDClient(port=2379)
    >> test_client.write('a', 'b')
    >> test_client.write('a/c', 'd')
    # Returns ('a', 'b')
    >> test_client.read('a')
    # Returns [('a', 'b'), ('a/c', 'd')]
    >> test_client.read_prefix('a')
"""

import json
import traceback
from contextlib import suppress
from typing import Generator, List, Optional, Tuple

from etcd3.client import Endpoint, MultiEndpointEtcd3Client

from skyshift.templates.event_template import WatchEventEnum

ETCD_PORT = 2379
DEFAULT_CLIENT_NAME = "/sky_registry/"


def _create_etcd3_client(port=ETCD_PORT):
    endpoint = Endpoint(host='127.0.0.1', port=port, secure=False)
    return MultiEndpointEtcd3Client(endpoints=[endpoint])


def remove_prefix(input_string: str, prefix: str = DEFAULT_CLIENT_NAME):
    """Removes prefix from input_string.
    Args:
        input_string: The string to remove the prefix from.
        prefix: The prefix to remove from the string.
    """
    # Keep removing the prefix as long as the string starts with it
    if input_string.startswith(prefix):
        input_string = input_string[len(prefix):]  # Remove the prefix
    return input_string


def convert_to_json(etcd_value: bytes) -> dict:
    """Converts etcd value to json dict.
    Args:
        etcd_value: The value to convert to json.
    Returns:
        The json dict.
    """
    etcd_dict = json.loads(etcd_value.decode("utf-8"))
    if isinstance(etcd_dict, str):
        etcd_dict = json.loads(etcd_dict)
    return etcd_dict


def get_resource_version(etcd_value: dict) -> int:
    """Gets the resource version from ETCD store.

    Args:
        etcd_value: The value to get the resource version from.
    Returns:
        The resource version.
    """
    if "metadata" not in etcd_value:
        return -1
    return etcd_value["metadata"].get("resource_version", None)


def update_resource_version(etcd_value: dict, resource_version: int) -> dict:
    """Updates the resource version in the ETCD store.

    Args:
        etcd_value: The value to update.
        resource_version: The resource version to update.
    Returns:
        The updated value.
    """
    if "metadata" not in etcd_value:
        etcd_value["metadata"] = {}
    etcd_value["metadata"]["resource_version"] = resource_version
    return etcd_value


def watch_generator_fn(
        watch_iter) -> Generator[Tuple[WatchEventEnum, dict], None, None]:
    """Generator function that yields ETCD watch events.

    Args:
        watch_iter: The watch iterator object.
    Returns:
        A generator that yields a tuple of WatchEventEnum and the value.
    """
    for event in watch_iter:
        grpc_event = event._event  # pylint: disable=protected-access
        if grpc_event.type == 0:
            # PUT event
            version = int(grpc_event.kv.version)
            if version == 1:
                event_type = WatchEventEnum.ADD
            elif version > 1:
                event_type = WatchEventEnum.UPDATE
            else:
                raise ValueError(f"Invalid version: {version}")
            key_value = grpc_event.kv
        elif grpc_event.type == 1:
            # DELETE event
            event_type = WatchEventEnum.DELETE
            key_value = grpc_event.prev_kv
        else:
            raise ValueError(f"Unknown event type: {event.type}")
        etcd_value = convert_to_json(key_value.value)
        etcd_value = update_resource_version(etcd_value,
                                             key_value.mod_revision)
        yield (event_type, etcd_value)


class ConflictError(Exception):
    """Exception raised when there is a conflict in the ETCD store."""

    def __init__(self, msg: str, resource_version: Optional[int] = None):
        self.msg = msg
        self.resource_version = resource_version
        super().__init__(self.msg)


class KeyNotFoundError(Exception):
    """Exception raised when a requested key does not exist."""

    def __init__(self,
                 key: str,
                 msg: str = "The requested key does not exist."):
        self.key = key
        self.msg = msg
        super().__init__(self.msg)


class ETCDClient:
    """ETCD client for Sky Manager, managed by the API server."""

    def __init__(self, log_name: str = DEFAULT_CLIENT_NAME, port=ETCD_PORT):
        self.log_name = log_name
        self.port = port
        self.etcd_client = _create_etcd3_client(port=port)

    def write(self, key: str, value: dict):
        """
        Write a key-value pairs to the etcd store.
        This method is threadsafe, with locks on all leaf nodes.
        Args:
            key (str): The key to write to.
            value (dict): The value to write to the key.
        """
        if self.log_name not in key:
            key = f"{self.log_name}{key}"
        try:
            self.etcd_client.put(key, json.dumps(value))
        except Exception as error:
            print(traceback.format_exc())
            raise error

    def update(self,
               key: str,
               value: dict,
               resource_version: Optional[int] = None):
        """
        Update a key-value pair in the etcd store. The key must exist.
        The update is only successful in the following two scenarios:
            1. The resource_version is not provided by the user, in which
            case we will override the prior resource_version stored in the
            etcd server.
            2. The resource_version is provided by the user, in which case
            we will compare the resource_version with the one stored in the
            etcd server. If the resource_version user provides is outdated,
            we will raise a ConflictError.

        Args:
            key (str): The key to update.
            value (dict): The value to update the key with.
            User DOES NOT need to provide the metadata in the dict.
            We will ignore it.
        """
        key = f"{self.log_name}{key}" if self.log_name not in key else key

        server_data = self.read(key)
        if server_data is None:
            raise KeyNotFoundError(
                f"Failed to update key `{key}` - Key does not exist.")

        if resource_version is None:
            # Override the prior value, this is ok.
            with suppress(Exception):
                self.etcd_client.put(key, json.dumps(value))
        else:
            success, _ = self.etcd_client.transaction(
                compare=[
                    self.etcd_client.transactions.mod(key) == resource_version
                ],
                success=[
                    self.etcd_client.transactions.put(key, json.dumps(value))
                ],
                failure=[],
            )

            if not success:
                raise ConflictError(
                    msg=f"Failed to update key `{key}` - \
                        resource version {resource_version} is outdated.",
                    resource_version=resource_version,
                )

    def read_prefix(self, key: str) -> List[dict]:
        """
        Read key-value pairs from the etcd store.
        Args:
            key (str): The key to read from.

        Returns:
            A list of values (dict) corresponds the key that has
            the prefix, with all metadata included (such as
            resource_version).

        """
        if self.log_name not in key:
            key = f"{self.log_name}{key}"
        kv_gen = self.etcd_client.get_prefix(key)
        read_list = []
        # If there are multiple descends from key.
        for kv_tuple in kv_gen:
            etcd_value = convert_to_json(kv_tuple[0])
            version_id = kv_tuple[1].mod_revision
            etcd_value = update_resource_version(etcd_value, version_id)
            read_list.append(etcd_value)
        return read_list

    def read(self, key: str):
        """
        Read key-value pairs from the etcd store.
        If key does not exist, return None.
        Args:
            key (str): The key to read from.

        Returns:
            The value (dict) corresponds the key, with all
            metadata included (such as resource_version).
        """
        if self.log_name not in key:
            key = f"{self.log_name}{key}"
        kv_tuple = self.etcd_client.get(key)
        if kv_tuple[0] is None:
            return None
        # Returns a json dictionary.
        etcd_value = convert_to_json(kv_tuple[0])
        version_id = kv_tuple[1].mod_revision
        # Adds resourve_version to the metadata.
        etcd_value = update_resource_version(etcd_value, version_id)
        return etcd_value

    def delete(self, key: str):
        """
        Remove a key-value pair (or all corresponding key values)
        from the etcd store.

        Args:
            key (str): The key to remove.
        """
        if self.log_name not in key:
            key = f"{self.log_name}{key}"
        etcd_response = self.etcd_client.delete(key,
                                                prev_kv=True,
                                                return_response=True)
        if etcd_response.deleted:
            assert len(etcd_response.prev_kvs) == 1
            key_value = etcd_response.prev_kvs[0]
            etcd_value = convert_to_json(key_value.value)
            etcd_value = update_resource_version(etcd_value,
                                                 key_value.mod_revision)
            return etcd_value
        raise KeyNotFoundError(
            key=key, msg=f"Failed to delete key `{key}` - Key does not exist.")

    def delete_prefix(self, key: str) -> List[dict]:
        """
        Remove a set of prefixed keys from the system.
        Args:
            key (str): The key to remove.
        Returns:
            A list of values (dict) corresponds the key that has
            the prefix, with all metadata included
            (such as resource_version).
        """
        if self.log_name not in key:
            key = f"{self.log_name}{key}"
        etcd_response = self.etcd_client.delete_prefix(key, prev_kv=True)  # pylint: disable=unexpected-keyword-arg
        if etcd_response.deleted:
            delete_list = []
            for key_value in etcd_response.prev_kvs:
                etcd_value = convert_to_json(key_value.value)
                etcd_value = update_resource_version(etcd_value,
                                                     key_value.mod_revision)
                delete_list.append(etcd_value)
            return delete_list
        return []

    def delete_all(self) -> List[dict]:
        """
        Remove all KVs from the system.
        Returns:
            A list of values (dict) corresponds the key that has the
            prefix, with all metadata included (such as resource_version).
        """
        return self.delete_prefix(self.log_name)

    def watch(self, key: str):
        """
        Watches over a set of keys (or a single key).
        Args:
            key: The key to watch.
        Returns:
            A generator that yields a tuple of WatchEventEnum and the
            value.
        """
        etcd_client = _create_etcd3_client(port=self.port)
        if self.log_name not in key:
            key = f"{self.log_name}{key}"

        watch_iter, cancel_fn = etcd_client.watch_prefix(key, prev_kv=True)
        return watch_generator_fn(watch_iter), cancel_fn
