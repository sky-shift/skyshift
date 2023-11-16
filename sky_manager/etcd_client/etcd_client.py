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
import traceback
from typing import List, Tuple

from etcd3.client import Etcd3Client

from sky_manager.etcd_client.monkey_patch import delete_prefix
from sky_manager.templates.event_template import WatchEventEnum

# Perform Monkey Patch over faulty Etcd3 Delete_Prefix method
Etcd3Client.delete_prefix = delete_prefix
ETCD_PORT = 2379
DEFAULT_CLIENT_NAME = '/sky_registry/'

def remove_prefix(input_string: str, prefix: str = DEFAULT_CLIENT_NAME):
    # Keep removing the prefix as long as the string starts with it
    if input_string.startswith(prefix):
        input_string = input_string[len(prefix):]  # Remove the prefix
    return input_string


class ETCDClient(object):
    """ETCD client for Sky Manager, managed by the API server."""

    def __init__(self, log_name: str = DEFAULT_CLIENT_NAME, port=ETCD_PORT):
        self.log_name = log_name
        self.port = port
        self.etcd_client = Etcd3Client(port=port)

    def write(self, key: str, value: str):
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
        # with self.etcd_client.lock(key):
        try:
            self.etcd_client.put(key, str(value))
        except Exception as e:
            print(traceback.format_exc())
            raise e

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
            value = kv_tuple[0].decode('utf-8')
            key_name = remove_prefix(kv_tuple[1].key.decode('utf-8'))
            read_list.append((key_name, value))
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
        key_name = remove_prefix(kv_tuple[1].key.decode('utf-8'))
        value = kv_tuple[0].decode('utf-8')
        return (key_name, value)

    def delete(self, key: str):
        """
        Remove a key-value pair (or all corresponding key values) from the
        etcd store.

        Returns:
        the deleted (key, value) if it exists, otherwise None.
        """
        if self.log_name not in key:
            key = f'{self.log_name}{key}'
        # with self.etcd_client.lock(key):
        etcd_response = self.etcd_client.delete(key, prev_kv=True, return_response=True)
        if etcd_response.deleted:
            assert len(etcd_response.prev_kvs) == 1
            kv = etcd_response.prev_kvs[0]
            return (
                remove_prefix(kv.key.decode('utf-8')),
                kv.value.decode('utf-8'),
            )
        return None

    def delete_prefix(self, key: str) -> List[Tuple[str, str]]:
        """
        Remove a set of prefixed keys from the system.

        Returns:
            A list of deleted (key, value) tuples, otherwise None.
        """
        if self.log_name not in key:
            key = f'{self.log_name}{key}'
        etcd_response =  self.etcd_client.delete_prefix(key, prev_kv=True)
        if etcd_response.deleted == 0:
            return None
        return [(
                    remove_prefix(kv.key.decode('utf-8')),
                    kv.value.decode('utf-8'),
                ) for kv in etcd_response.prev_kvs]

    def delete_all(self) -> List[Tuple[str, str]]:
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
        watch_iter, cancel_fn = self.etcd_client.watch_prefix(key, prev_kv=True)
        return self._process_watch_iter(watch_iter), cancel_fn

    def _process_watch_iter(self, watch_iter) -> Tuple[str, str, str]:
        for event in watch_iter:
            grpc_event = event._event
            if grpc_event.type == 0:
                # PUT event
                version =  int(grpc_event.kv.version)
                if version == 1:
                     event_type = WatchEventEnum.ADD
                elif version > 1:
                     event_type = WatchEventEnum.UPDATE
                else:
                    raise ValueError(f'Invalid version: {version}')
                key = grpc_event.kv.key.decode('utf-8')
                value = grpc_event.kv.value.decode('utf-8')
            elif grpc_event.type == 1:
                # DELETE event
                event_type = WatchEventEnum.DELETE
                key = grpc_event.prev_kv.key.decode('utf-8')
                value = grpc_event.prev_kv.value.decode('utf-8')
            else:
                raise ValueError(f'Unknown event type: {event.type}')
            key = remove_prefix(key)
            yield (event_type, key, value)
