"""
Tests for ETCD interface.
"""

import os
import random
import string
import subprocess
import tempfile
import threading
import time
from typing import Set

import pytest

from skyflow.etcd_client.etcd_client import (ConflictError, ETCDClient,
                                             KeyNotFoundError,
                                             get_resource_version)
from skyflow.tests.tests_utils import (retrieve_current_working_dir,
                                       setup_skyflow, shutdown_skyflow)

# NOTE:
# In the following test, we assume that the key for the value dictionary is always "value_key". This is hard-coded.

# To run the test, use the following command:
# pytest skyflow/tests/test_etcd_client.py


@pytest.fixture(scope="module")
def etcd_client():
    with tempfile.TemporaryDirectory() as temp_data_dir:
        print("Using temporary data directory for ETCD:", temp_data_dir)

        current_file_path = os.path.abspath(__file__)
        current_directory = os.path.dirname(current_file_path)
        relative_path_to_script = "../../api_server/install_etcd.sh"
        install_script_path = os.path.abspath(
            os.path.join(current_directory, relative_path_to_script))

        data_directory = temp_data_dir

        command = [
            "bash",
            install_script_path,
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


## For Basic Functionality ##
def generate_random_string(min_length=10, max_length=100):
    key_length = random.randint(min_length, max_length)
    key = "".join(
        random.choices(string.ascii_letters + string.digits, k=key_length))

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


def generate_random_resource_version(old_resource_version, num=1):
    if num == 1:
        new_resource_version = random.randint(1, 100000)
        while new_resource_version == old_resource_version or new_resource_version == old_resource_version + 1:
            new_resource_version = random.randint(1, 100000)
        return new_resource_version
    result = []
    for _ in range(num):
        new_resource_version = random.randint(1, 100000)
        while new_resource_version == old_resource_version or new_resource_version in result or new_resource_version - 1 in result:
            new_resource_version = random.randint(1, 100000)
        result.append(new_resource_version)
    return result


def generate_prefix_key(num=5, ensure_uniqueness=True):
    prefix = generate_random_string(5, 10)
    result = []
    for _ in range(num):
        result.append(prefix + "_" + generate_random_string(10, 20))
        used_keys.add(result[-1])
    return prefix, result


## For Concurrency Test ##
def concurrent_write(client, key, thread_id, barrier):
    value_dict = {"value_key": thread_id}
    barrier.wait()  # Wait for all threads to be ready
    client.write(key, value_dict)


def concurrent_read(client, key, expect_value, barrier):
    barrier.wait()  # Wait for all threads to be ready
    assert client.read(key)["value_key"] == expect_value


def concurrent_update(client, key, resource_version, chosen_index, thread_id,
                      barrier):
    value_dict = {"value_key": thread_id}
    barrier.wait()  # Wait for all threads to be ready
    if thread_id == chosen_index:
        client.update(key, value_dict, resource_version)
    else:
        resource_version = generate_random_resource_version(resource_version)
        with pytest.raises(ConflictError):
            client.update(key, value_dict, resource_version)


## For Stress Test ##
def write_worker(etcd_client, keys_list, values_list, thread_id):
    """Worker function for writing data to the ETCD store."""
    worker_keys_list = keys_list[thread_id::NUM_THREADS]
    worker_values_list = values_list[thread_id::NUM_THREADS]
    for key, value in zip(worker_keys_list, worker_values_list):
        etcd_client.write(key, value)


def update_worker(etcd_client, keys_list, values_list, metadata_list,
                  update_index, thread_id):
    """Worker function for updating data in the ETCD store."""
    worker_update_index = update_index[thread_id::NUM_THREADS]
    for index in worker_update_index:
        etcd_client.update(keys_list[index], values_list[index],
                           metadata_list[index])


def check_data_integrity(etcd_client, keys_list, values_list):
    """Check that the data in the ETCD store matches the expected data. Return the metadata list for further testing."""
    metadata_list = []
    for key, value in zip(keys_list, values_list):
        read_value = etcd_client.read(key)
        assert read_value["value_key"] == value["value_key"]
        metadata_list.append(get_resource_version(read_value))
    return metadata_list


#### Test Section ####

used_keys: Set[str] = set()  # This is to ensure that the keys are unique.
NUM_THREADS = 50
NUM_OPERATIONS_PER_THREAD = 1000


def test_simple_read_write_update(etcd_client):

    # Test writing a key-value pair to the store and assert it's correctly stored.
    # Test reading a previously written key-value pair.
    key = generate_random_key()
    write_value = generate_random_value_dict()
    etcd_client.write(key, write_value)
    read_value = etcd_client.read(
        key)  # This contains the resource_version metadata.

    assert (read_value["value_key"] == write_value["value_key"])

    # Test reading a non-existent key, expect KeyNotFoundError.
    new_key = generate_random_key()

    assert etcd_client.read(new_key) == None

    # Test conditional updating an existing key based on resource versions to ensure concurrency control.
    new_value = generate_random_value_dict()
    old_resource_version = get_resource_version(read_value)
    etcd_client.update(key, new_value, get_resource_version(read_value))
    read_value = etcd_client.read(key)

    assert (read_value["value_key"] == new_value["value_key"])

    # Test conditional updating an existing key with the old resource_version, expect ConflictError.
    assert old_resource_version != get_resource_version(read_value)

    new_value = generate_random_value_dict()

    with pytest.raises(ConflictError):
        etcd_client.update(key, new_value, old_resource_version)

    # Test updating an existing key that doesn't have resource_version, aka. test for bypasses optimistic concurrency control.
    new_value = generate_random_value_dict()

    etcd_client.update(key, new_value)

    assert (etcd_client.read(key)["value_key"] == new_value["value_key"])
    assert (get_resource_version(etcd_client.read(key)) >
            get_resource_version(read_value))

    # Test conditional updating an existing key with the wrong resource_version, expect ConflictError.
    new_value = generate_random_value_dict()
    new_resource_version = generate_random_resource_version(
        get_resource_version(read_value))

    with pytest.raises(ConflictError):
        etcd_client.update(key, new_value, new_resource_version)

    # Test updating a non-existent key, expect KeyNotFoundError.
    new_key = generate_random_key()

    with pytest.raises(KeyNotFoundError):
        etcd_client.update(new_key, new_value)

    assert etcd_client.read(new_key) == None


def test_simple_delete(etcd_client):

    key = generate_random_key()
    write_value = generate_random_value_dict()
    etcd_client.write(key, write_value)
    read_value = etcd_client.read(
        key)  # This contains the resource_version metadata.

    assert (read_value["value_key"] == write_value["value_key"])

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

    prefix_2, keys_2 = generate_prefix_key(
        10)  # This is to create some keys that are not part of the prefix.
    write_values_2 = [generate_random_value_dict() for _ in range(len(keys_2))]
    for i in range(len(keys_2)):
        etcd_client.write(keys_2[i], write_values_2[i])

    read_values_expected = []
    for i in range(len(keys_1)):
        read_value = etcd_client.read(keys_1[i])
        assert (read_value["value_key"] == write_values_1[i]["value_key"])
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
    assert sorted(etcd_client.read_prefix(prefix_1),
                  key=lambda x: x['value_key']) == read_values_expected


def test_delete_all(etcd_client):

    # Test deleting all keys and verify the store is empty.
    etcd_client.delete_all()

    assert len(etcd_client.read_prefix("")) == 0


def test_concurrent_read_write_update(etcd_client):
    # Simulate multiple clients performing concurrent operations on the same keys to verify proper synchronization and conflict resolution mechanisms.

    key = generate_random_key()
    barrier = threading.Barrier(NUM_THREADS)

    threads = [
        threading.Thread(target=concurrent_write,
                         args=(etcd_client, key, i, barrier))
        for i in range(NUM_THREADS)
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    final_value = etcd_client.read(key)

    # Test concurrent reads to verify the final value is consistent.
    barrier.reset()
    threads = [
        threading.Thread(target=concurrent_read,
                         args=(etcd_client, key, final_value["value_key"],
                               barrier)) for i in range(NUM_THREADS)
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    # Test concurrent conditional updates to verify the final value is consistent.
    # Only 1 thread will get the correct resource_version and update the value. All other threads should fail.
    barrier.reset()
    chosen_index = random.randint(0, NUM_THREADS - 1)
    old_version = get_resource_version(final_value)
    threads = [
        threading.Thread(target=concurrent_update,
                         args=(etcd_client, key, old_version, chosen_index, i,
                               barrier)) for i in range(NUM_THREADS)
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    assert old_version + 1 == get_resource_version(etcd_client.read(key))
    assert etcd_client.read(key)["value_key"] == chosen_index


def test_concurrent_access(etcd_client):
    # Stress Test the ETCD client by simulating concurrent read, write and update operations.

    prefix_list = []
    keys_list = []
    values_list = []

    for i in range(NUM_THREADS):
        prefix, keys = generate_prefix_key(NUM_OPERATIONS_PER_THREAD)
        prefix_list.append(prefix)
        keys_list.extend(keys)

    values_list = [
        generate_random_value_dict()
        for _ in range(NUM_THREADS * NUM_OPERATIONS_PER_THREAD)
    ]

    # Start threads for concurrent write
    threads = [
        threading.Thread(target=write_worker,
                         args=(etcd_client, keys_list, values_list, i))
        for i in range(NUM_THREADS)
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    # Verify data integrity
    metadata_list = check_data_integrity(etcd_client, keys_list, values_list)

    # Select a subset for batch update
    update_index = random.sample(
        range(NUM_THREADS * NUM_OPERATIONS_PER_THREAD),
        10 * NUM_OPERATIONS_PER_THREAD)
    for i in update_index:
        values_list[i] = generate_random_value_dict()

    update_thread = [
        threading.Thread(target=update_worker,
                         args=(etcd_client, keys_list, values_list,
                               metadata_list, update_index, i))
        for i in range(NUM_THREADS)
    ]

    for thread in update_thread:
        thread.start()

    for thread in update_thread:
        thread.join()

    # Verify data integrity
    check_data_integrity(etcd_client, keys_list, values_list)


"""
TODO:
Future Improvements:

Thread Safety
Test concurrent reads and writes to verify the thread safety of the client.

Performance Benchmarks
Measure the latency and throughput of CRUD operations under various load conditions to ensure the client meets performance requirements.

End-to-End CRUD Operations
Perform a series of CRUD operations in a specific sequence to verify the system behaves as expected in a real-world scenario.

Recovery and Fault Tolerance
Test the client's ability to handle network failures, ETCD cluster failures, and other unexpected errors gracefully.

Stress Testing
Stress the ETCD server by performing a high volume of operations over an extended period to identify potential bottlenecks or memory leaks.

Scalability Testing
Verify that the ETCD client scales well with the size of the data and the number of clients, ensuring performance doesn't degrade unexpectedly.

Longevity Testing
Run the ETCD client continuously under a moderate load for an extended period to ensure there are no issues with long-term operation, such as resource leaks.
"""
