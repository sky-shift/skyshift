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

from skyflow.etcd_client.etcd_client import ETCDClient, get_resource_version, ConflictError, KeyNotFoundError

# NOTE:
# In the following test, we assume that the key for the value dictionary is always "value_key". This is hard-coded.

"""
TODO:
Unit Tests
Initialization Test
Test if the ETCDClient initializes with the correct default and custom parameters.

Thread Safety
Test concurrent reads and writes to verify the thread safety of the client.

Concurrent Access Patterns
Simulate multiple clients performing concurrent operations on the same keys to verify proper synchronization and conflict resolution mechanisms.
Performance Benchmarks
Measure the latency and throughput of CRUD operations under various load conditions to ensure the client meets performance requirements.
End-to-End CRUD Operations
Perform a series of CRUD operations in a specific sequence to verify the system behaves as expected in a real-world scenario.
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
        # FIXME: We might need to change the path to "api_server/install_etcd.sh"
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


#### Helper methods ####

def generate_random_string(min_length=10, max_length=100):
    key_length = random.randint(min_length, max_length)
    key = "".join(random.choices(string.ascii_letters + string.digits, k=key_length))

    return key


def generate_random_key():
    key = generate_random_string(10, 20)
    while key in used_keys:
        key = generate_random_string(10, 20)
    used_keys.add(key)
    
    return key


def generate_random_value_dict():
    value = {"value_key": generate_random_string(20, 100)}

    return value


def generate_random_value_dict_keep_metadata(target_value_dict):
    new_value = generate_random_string(20, 100)
    while new_value == target_value_dict["value_key"]:
        new_value = generate_random_string(20, 100)
    target_value_dict["value_key"] = new_value

    return target_value_dict

def generate_random_resource_version(old_resource_version):
    new_resource_version = random.randint(1, 10000)
    while new_resource_version == old_resource_version:
        new_resource_version = random.randint(1, 10000)
    return new_resource_version


def generate_prefix_key(num=5):
    prefix = generate_random_string(5, 10)
    result = []
    for _ in range(num):
        result.append(prefix + "_" + generate_random_string(10, 20))
        used_keys.add(result[-1])
    return prefix, result


used_keys = set()  # Keep track of used keys to ensure uniqueness throughout the tests.


#### Test Section ####

def test_simple_read_write_update(etcd_client):
    
    # Test writing a key-value pair to the store and assert it's correctly stored.
    # Test reading a previously written key-value pair.
    key = generate_random_key()
    write_value = generate_random_value_dict()
    etcd_client.write(key, write_value)
    read_value = etcd_client.read(key)  # This contains the resource_version metadata.

    assert (
        read_value["value_key"] == write_value["value_key"]
    )


    # Test reading a non-existent key, expect KeyNotFoundError.
    new_key = generate_random_key()

    assert etcd_client.read(new_key) == None


    # Test conditional updating an existing key based on resource versions to ensure concurrency control.
    new_value = generate_random_value_dict()
    etcd_client.update(key, new_value, get_resource_version(read_value))

    assert (
        etcd_client.read(key)["value_key"] == new_value["value_key"]
    )


    # Test updating an existing key that doesn't have resource_version, aka. test for bypasses optimistic concurrency control.
    new_value = generate_random_value_dict()

    etcd_client.update(key, new_value)

    assert (
        etcd_client.read(key)["value_key"] == new_value["value_key"]
    )
    assert (get_resource_version(etcd_client.read(key)) > get_resource_version(read_value))
    
    
    # Test conditional updating an existing key with the wrong resource_version, expect ConflictError.
    new_value = generate_random_value_dict()
    ner_resource_version = generate_random_resource_version(get_resource_version(read_value))
    
    with pytest.raises(ConflictError):
        etcd_client.update(key, new_value, ner_resource_version)


    # Test updating a non-existent key, expect KeyNotFoundError.
    new_key = generate_random_key()
    
    with pytest.raises(KeyNotFoundError):
        etcd_client.update(new_key, new_value) 
    
    assert etcd_client.read(new_key) == None
    
    
def test_simple_delete(etcd_client):

    key = generate_random_key()
    write_value = generate_random_value_dict()
    etcd_client.write(key, write_value)
    read_value = etcd_client.read(key)  # This contains the resource_version metadata.

    assert (
        read_value["value_key"] == write_value["value_key"]
    )

    # Test deleting a non-existent key, expect KeyNotFoundError.
    with pytest.raises(KeyNotFoundError):
        etcd_client.delete(generate_random_key())
        
    # Test deleting an existing key and verify it's removed from the store.
    etcd_client.delete(key)
    
    assert etcd_client.read(key) == None
        
        
def test_simple_prefix_read_delete(etcd_client):
    # Read using prefix_1, then delete using prefix_2.
    
    prefix_1, keys_1 = generate_prefix_key(10)
    write_values_1 = [generate_random_value_dict() for _ in range(len(keys_1))]
    for i in range(len(keys_1)):
        etcd_client.write(keys_1[i], write_values_1[i])
        
    prefix_2, keys_2 = generate_prefix_key(10) # This is to create some keys that are not part of the prefix.
    write_values_2 = [generate_random_value_dict() for _ in range(len(keys_2))]
    for i in range(len(keys_2)):
        etcd_client.write(keys_2[i], write_values_2[i])
        
    read_values_expected = []
    for i in range(len(keys_1)):
        read_value = etcd_client.read(keys_1[i])
        assert (
            read_value["value_key"] == write_values_1[i]["value_key"]
        )
        read_values_expected.append(read_value)
    read_values_expected.sort(key=lambda x: x['value_key'])
     
    
    # Test reading keys with a specific prefix to ensure it returns all matching key-value pairs.
    read_prefix_result = etcd_client.read_prefix(prefix_1)
    read_prefix_result.sort(key=lambda x: x['value_key'])
    
    assert len(read_prefix_result) == len(keys_1)
    assert read_prefix_result == read_values_expected

    
    # Test reading with a non-existent prefix to verify it returns an empty list or appropriate response.
    new_key = generate_random_key()
    
    assert etcd_client.read_prefix(new_key) == []
    
    
    # Test deleting with a non-existent prefix to ensure no unintended deletions occur.
    new_key = generate_random_key()
    
    assert etcd_client.delete_prefix(new_key) == []
    
    for i in range(len(keys_1)):
        assert etcd_client.read(keys_1[i]) != None
    for i in range(len(keys_2)):
        assert etcd_client.read(keys_2[i]) != None
    
    
    # Test deleting keys with a specific prefix and verify all matching keys are removed.
    delete_prefix_result_expected = etcd_client.read_prefix(prefix_2)
    delete_prefix_result_expected.sort(key=lambda x: x['value_key'])
    
    delete_prefix_result = etcd_client.delete_prefix(prefix_2)
    delete_prefix_result.sort(key=lambda x: x['value_key'])
    
    assert len(delete_prefix_result) == len(keys_2)
    assert delete_prefix_result == delete_prefix_result_expected
    for i in range(len(keys_2)):
        assert etcd_client.read(keys_2[i]) == None
        
    assert etcd_client.read_prefix(prefix_2) == []
    assert sorted(etcd_client.read_prefix(prefix_1), key=lambda x: x['value_key']) == read_values_expected


def test_delete_all(etcd_client):
    
    # Test deleting all keys and verify the store is empty.
    etcd_client.delete_all()
    
    assert len(etcd_client.read_prefix("")) == 0
    
    
    


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
