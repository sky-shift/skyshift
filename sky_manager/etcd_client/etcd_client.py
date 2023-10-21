import traceback

import etcd3 as etcd

ETCD_PORT = 2379
DEFAULT_CLIENT_NAME = '/sky_registry'


class ETCDClient(object):
    """ETCD client for Sky Manager, managed by the API server.
    """

    def __init__(self, log_name: str = DEFAULT_CLIENT_NAME, port=ETCD_PORT):
        self.log_name = log_name
        self.port = port
        self.etcd_client = etcd.client(port=port)

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
            key = f'{self.log_name}/{key}'
        with self.etcd_client.lock(key):
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
            key = f'{self.log_name}/{key}'
        kv_gen = self.etcd_client.get_prefix(key)
        read_list = []
        # If there are multiple descends from key.
        for kv_tuple in kv_gen:
            value = kv_tuple[0].decode('utf-8')
            key_name = kv_tuple[1].key.decode('utf-8')
            read_list.append((key_name, value))
        return read_list

    def read(self, key: str):
        """
        Read key-value pairs from the etcd store.

        Args:
            key (str): The key to read from.
        """
        if self.log_name not in key:
            key = f'{self.log_name}/{key}'
        kv_tuple = self.etcd_client.get(key)
        if kv_tuple[0] is None:
            return None
        key_name = kv_tuple[1].key.decode('utf-8')
        value = kv_tuple[0].decode('utf-8')
        return (key_name, value)

    def delete(self, key: str):
        """
        Remove a key-value pair (or all corresponding key values) from the
        etcd store.
        """
        if self.log_name not in key:
            key = f'{self.log_name}/{key}'
        return self.etcd_client.delete(key, prev_kv=True)

    def delete_prefix(self, key: str):
        """
        Remove a keys from the system.
        """
        if self.log_name not in key:
            key = f'{self.log_name}/{key}'
        return self.etcd_client.delete_prefix(key)

    def delete_all(self):
        """
        Remove a keys from the system.
        """
        return self.etcd_client.delete_prefix(self.log_name)

    def watch(self, key: str):
        if self.log_name not in key:
            key = f'{self.log_name}/{key}'
        return self.etcd_client.watch_prefix(key, prev_kv=True)
