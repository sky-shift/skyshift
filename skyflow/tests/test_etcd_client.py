"""
Tests for ETCD interface.
"""

import json
import random
import string
import subprocess
import tempfile
import threading
import time

import pytest

from skyflow.etcd_client.etcd_client import ETCDClient


@pytest.fixture(scope="module")
def etcd_client():
    with tempfile.TemporaryDirectory() as temp_data_dir:
        print("Using temporary data directory for ETCD:", temp_data_dir)
        data_directory = temp_data_dir
        command = [
            "bash",
            "../../api_server/install_etcd.sh",
            data_directory,
        ]

        process = subprocess.Popen(command)
        time.sleep(5)  # Wait for the server to start

        client = ETCDClient()
        yield client  # Test execution happens here

        # Stop the application and ETCD server
        process.terminate()
        process.wait()
        print("Cleaned up temporary ETCD data directory.")


def test_simple_write_and_read(etcd_client):
    #
    key = "test/key"
    value = {"data222": "test_value"}
    etcd_client.write(key, value)
    read_value = etcd_client.read(key)
    print("hello")
    print(value)
    print(read_value)
    assert read_value == value, "Read value should match written value"

    # Test read non-existent key
    key = "test/nonexistent_key"
    assert etcd_client.read(
        key) == None, "Read value should be None for non-existent key"


# def generate_random_data(n=1000):
#     """Generate n unique key-value pairs."""
#     data = {}
#     generated_keys = set()
#     while len(data) < n:
#         key_length = random.randint(5, 20)
#         key = ''.join(
#             random.choices(string.ascii_letters + string.digits, k=key_length))
#         # Ensure key uniqueness
#         if key not in generated_keys:
#             value_length = random.randint(5, 100)
#             value = {
#                 'data':
#                 ''.join(
#                     random.choices(string.ascii_letters + string.digits,
#                                    k=value_length))
#             }
#             data[key] = value
#             generated_keys.add(key)
#     return data


# def generate_new_value(old_value):
#     """Generate a new value based on the old value."""
#     new_value_length = random.randint(5, 100)
#     new_data = ''.join(
#         random.choices(string.ascii_letters + string.digits,
#                        k=new_value_length))
#     return {'data': new_data}


# def write_worker(etcd_client, data):
#     """Worker function for writing data to the ETCD store."""
#     for key, value in data.items():
#         etcd_client.write(key, value)


# def update_worker(etcd_client, data):
#     """Worker function for updating data in the ETCD store."""
#     for key, value in data.items():
#         etcd_client.update(key, value)


# def check_data_integrity(etcd_client, data):
#     """Check that the data in the ETCD store matches the expected data."""
#     for key, value in data.items():
#         read_value = etcd_client.read(key)
#         assert read_value == value, "Read value should match written value"


# def test_concurrent_access(etcd_client):
#     data = generate_random_data(10000)
#     data_items = list(data.items())
#     random.shuffle(data_items)

#     num_workers = 16

#     # Split data among workers for concurrent write
#     data_chunks = [
#         dict(data_items[i::num_workers]) for i in range(num_workers)
#     ]

#     # Start threads for concurrent write
#     threads = [
#         threading.Thread(target=write_worker, args=(etcd_client, chunk))
#         for chunk in data_chunks
#     ]
#     for thread in threads:
#         thread.start()
#     for thread in threads:
#         thread.join()

#     # Select a subset for batch update
#     update_subset = dict(random.sample(data_items, 2000))
#     update_data = {
#         key: generate_new_value(value)
#         for key, value in update_subset
#     }
#     update_data_chunks = [
#         dict(list(update_data.items())[i::num_workers])
#         for i in range(num_workers)
#     ]
#     update_thread = [
#         threading.Thread(target=update_worker, args=(etcd_client, chunk))
#         for chunk in update_data_chunks
#     ]
#     for thread in update_thread:
#         thread.start()
#     for thread in update_thread:
#         thread.join()

#     # Verify data integrity
#     combined_data = {**data, **update_data}
#     check_data_integrity(etcd_client, combined_data)
