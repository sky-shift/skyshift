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

# NOTE:
# In the following test, we assume that the key for the value dictionary is always "value_key". This is hard-coded.

"""
Unit Tests
Initialization Test
Test if the ETCDClient initializes with the correct default and custom parameters.

Delete Operation
Test deleting an existing key and verify it's removed from the store.
Test deleting a non-existent key to ensure it handles the operation gracefully.
Delete Prefix Operation
Test deleting keys with a specific prefix and verify all matching keys are removed.
Test deleting with a non-existent prefix to ensure no unintended deletions occur.
Read Prefix Operation
Test reading keys with a specific prefix to ensure it returns all matching key-value pairs.
Test reading with a non-existent prefix to verify it returns an empty list or appropriate response.
Conflict Error Handling
Test the update operation with an outdated resource version to ensure it raises a ConflictError.
Thread Safety
Test concurrent reads and writes to verify the thread safety of the client.
Integration Tests
End-to-End CRUD Operations
Perform a series of CRUD operations in a specific sequence to verify the system behaves as expected in a real-world scenario.
Concurrent Access Patterns
Simulate multiple clients performing concurrent operations on the same keys to verify proper synchronization and conflict resolution mechanisms.
Performance Benchmarks
Measure the latency and throughput of CRUD operations under various load conditions to ensure the client meets performance requirements.
Recovery and Fault Tolerance
Test the client's ability to handle network failures, ETCD cluster failures, and other unexpected errors gracefully.
Security and Authentication
If applicable, test that the client correctly implements security measures such as TLS encryption and authentication mechanisms.
Load Tests
Stress Testing
Stress the ETCD server by performing a high volume of operations over an extended period to identify potential bottlenecks or memory leaks.
Scalability Testing
Verify that the ETCD client scales well with the size of the data and the number of clients, ensuring performance doesn't degrade unexpectedly.
Longevity Testing
Run the ETCD client continuously under a moderate load for an extended period to ensure there are no issues with long-term operation, such as resource leaks.
"""


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


def generate_random_string(min_length=10, max_length=100):
    key_length = random.randint(min_length, max_length)
    key = "".join(random.choices(string.ascii_letters + string.digits, k=key_length))

    return key


def generate_random_key(used_keys):
    key = generate_random_string(10, 20)
    while key in used_keys:
        key = generate_random_string(10, 20)
    used_keys.add(key)
    
    return key


def generate_random_value_dict():
    value = {"value_key": generate_random_string(20, 100)}

    return value


def generate_random_value_dict_keep_metainfo(target_value_dict):
    new_value = generate_random_string(20, 100)
    while new_value == target_value_dict["value_key"]:
        new_value = generate_random_string(20, 100)
    target_value_dict["value_key"] = new_value

    return target_value_dict


def test_simple(etcd_client):
    used_keys = set()
    
    # Test writing a key-value pair to the store and assert it's correctly stored.
    # Test reading a previously written key-value pair.
    key = generate_random_key(used_keys)
    write_value = generate_random_value_dict()
    etcd_client.write(key, write_value)
    read_value = etcd_client.read(key)

    assert (
        read_value["value_key"] == write_value["value_key"]
    ), "Test simple write and read operations."


    # Test reading a non-existent key to ensure it returns None.
    new_key = generate_random_key(used_keys)

    assert etcd_client.read(new_key) == None, "Test reading a non-existent key."


    # Test updating an existing key with a new value that has resource_version and verify if the update is successful.
    read_value = generate_random_value_dict_keep_metainfo(read_value)
    etcd_client.update(key, read_value)

    assert (
        etcd_client.read(key)["value_key"] == read_value["value_key"]
    ), "Test updating an existing key with a new value that has resource_version."


    # Test updating an existing key with a new value and verify if the update is successful.
    new_value = generate_random_value_dict()

    etcd_client.update(key, new_value)

    assert (
        etcd_client.read(key)["value_key"] == new_value["value_key"]
    ), "Test updating an existing key with a new value that doesn't have resource_version, aka. test for bypasses optimistic concurrency control."


    # Test updating a non-existent key to ensure proper handling of the error or response.
    new_key = generate_random_key(used_keys)
    etcd_client.update(new_key, new_value) # This should fail, why not?
    
    assert etcd_client.read(new_key) == None, "Test updating a non-existent key."
    
    
    # Test conditional updates based on resource versions to ensure concurrency control.
    


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
