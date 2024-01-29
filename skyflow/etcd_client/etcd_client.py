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
from typing import Generator, List, Optional, Tuple

from etcd3.client import Etcd3Client

from skyflow.etcd_client.monkey_patch import delete_prefix
from skyflow.templates.event_template import WatchEventEnum

# Perform Monkey Patch over faulty Etcd3 Delete_Prefix method
Etcd3Client.delete_prefix = delete_prefix
ETCD_PORT = 2379
DEFAULT_CLIENT_NAME = '/sky_registry/'


def remove_prefix(input_string: str, prefix: str = DEFAULT_CLIENT_NAME):
    # Keep removing the prefix as long as the string starts with it
    if input_string.startswith(prefix):
        input_string = input_string[len(prefix):]  # Remove the prefix
    return input_string


def convert_to_json(etcd_value: bytes) -> dict:
    etcd_dict = json.loads(etcd_value.decode('utf-8'))
    if isinstance(etcd_dict, str):
        etcd_dict = json.loads(etcd_dict)
    return etcd_dict


def get_resource_version(etcd_value: dict) -> int:
    if 'metadata' not in etcd_value:
        return -1
    return etcd_value['metadata'].get('resource_version', None)


def update_resource_version(etcd_value: dict, resource_version: int) -> dict:
    if 'metadata' not in etcd_value:
        etcd_value['metadata'] = {}
    etcd_value['metadata']['resource_version'] = resource_version
    return etcd_value


class ConflictError(Exception):

    def __init__(self, msg: str, resource_version: Optional[int] = None):
        self.msg = msg
        self.resource_version = resource_version
        super().__init__(self.msg)


class ETCDClient(object):
    """ETCD client for Sky Manager, managed by the API server."""

    def __init__(self, log_name: str = DEFAULT_CLIENT_NAME, port=ETCD_PORT):
        self.log_name = log_name
        self.port = port
        self.etcd_client = Etcd3Client(port=port)

    def write(self, key: str, value: dict):
        """
        Write a key-value pairs to the etcd store.

        If value is a dict, recursively write the key-value pairs.
        This method is threadsafe, with locks on all leaf nodes.

        Args:
            key (str): The key to write to.
            value (str): The value to write to the key.
        """
        if self.log_name not in key:
            key = f'{self.log_name}{key}'
        try:
            self.etcd_client.put(key, json.dumps(value))
        except Exception as e:
            print(traceback.format_exc())
            raise e

    def update(self,
               key: str,
               value: dict,
               resource_version: Optional[int] = None):
        """
        Update a key-value pair in the etcd store.

        Args:
            key (str): The key to update.
            value (str): The value to update the key with.
        """
        if not resource_version:
            resource_version = get_resource_version(value)
        if self.log_name not in key:
            key = f'{self.log_name}{key}'
        try:
            if resource_version != -1:
                # Override the prior value, this is ok.
                self.etcd_client.put(key, json.dumps(value))
                success = True
            else:
                success, _ = self.etcd_client.transaction(
                    compare=[
                        self.etcd_client.transactions.mod(key) ==
                        resource_version
                    ],
                    success=[
                        self.etcd_client.transactions.put(
                            key, json.dumps(value))
                    ],
                    failure=[])
        except Exception as e:
            print(traceback.format_exc())
            raise e

        if not success:
            raise ConflictError(
                msg=
                f"Failed to update key `{key}` - resource version {resource_version} is outdated.",
                resource_version=resource_version,
            )

    def read_prefix(self, key: str):
        """
        Read key-value pairs from the etcd store.

        Args:
            key (str): The key to read from.
        """
        if self.log_name not in key:
            key = f'{self.log_name}{key}'
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

        Args:
            key (str): The key to read from.
        """
        if self.log_name not in key:
            key = f'{self.log_name}{key}'
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
        Remove a key-value pair (or all corresponding key values) from the
        etcd store.

        Returns:
        the deleted (key, value) if it exists, otherwise None.
        """
        if self.log_name not in key:
            key = f'{self.log_name}{key}'
        etcd_response = self.etcd_client.delete(key,
                                                prev_kv=True,
                                                return_response=True)
        if etcd_response.deleted:
            assert len(etcd_response.prev_kvs) == 1
            kv = etcd_response.prev_kvs[0]
            etcd_value = convert_to_json(kv.value)
            etcd_value = update_resource_version(etcd_value, kv.mod_revision)
            return etcd_value
        return None

    def delete_prefix(self, key: str) -> List[dict]:
        """
        Remove a set of prefixed keys from the system.

        Returns:
            A list of deleted (key, value) tuples, otherwise None.
        """
        if self.log_name not in key:
            key = f'{self.log_name}{key}'
        etcd_response = self.etcd_client.delete_prefix(key, prev_kv=True)
        if etcd_response.deleted:
            delete_list = []
            for kv in etcd_response.prev_kvs:
                etcd_value = convert_to_json(kv.value)
                etcd_value = update_resource_version(etcd_value,
                                                     kv.mod_revision)
                delete_list.append(etcd_value)
            return delete_list
        return []

    def delete_all(self) -> List[dict]:
        """
        Remove all KVs from the system.

        Returns:
            A list containing all deleted KV pairs.
        """
        return self.delete_prefix(self.log_name)

    def watch(self, key: str):
        """
        Watches over a set of keys (or a single key).

        Returns:
            A generator that yields (event_type, key, value) tuples.
        """
        if self.log_name not in key:
            key = f'{self.log_name}{key}'
        watch_iter, cancel_fn = self.etcd_client.watch_prefix(key,
                                                              prev_kv=True)
        return self._process_watch_iter(watch_iter), cancel_fn

    def _process_watch_iter(
            self,
            watch_iter) -> Generator[Tuple[WatchEventEnum, dict], None, None]:
        for event in watch_iter:
            grpc_event = event._event
            if grpc_event.type == 0:
                # PUT event
                version = int(grpc_event.kv.version)
                if version == 1:
                    event_type = WatchEventEnum.ADD
                elif version > 1:
                    event_type = WatchEventEnum.UPDATE
                else:
                    raise ValueError(f'Invalid version: {version}')
                kv = grpc_event.kv
            elif grpc_event.type == 1:
                # DELETE event
                event_type = WatchEventEnum.DELETE
                kv = grpc_event.prev_kv
            else:
                raise ValueError(f'Unknown event type: {event.type}')
            etcd_value = convert_to_json(kv.value)
            etcd_value = update_resource_version(etcd_value, kv.mod_revision)
            yield (event_type, etcd_value)


if __name__ == '__main__':
    etcd_client = ETCDClient()
    new_value = {"b": 3}
    etcd_client.write("a", {"a": 2})
    original_value = etcd_client.read("a")
    etcd_client.update("a", new_value)
    etcd_client.update("a", new_value, resource_version=1)
    new_value = etcd_client.read("a")
    print(new_value)
