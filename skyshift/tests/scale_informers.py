"""Evaluation script to test scaling of parallel informers watches over API server."""
import logging
import threading
import time

from skyshift.api_client import ClusterAPI, JobAPI
from skyshift.api_client.object_api import APIException, ObjectAPI
from skyshift.structs.informer import Informer

LOCK = threading.Lock()
UPDATE_COUNTER = 0


def launch_informer(idx: int):
    """Thread function that launches an informer."""
    # Create logger with idx
    logger = logging.getLogger(f"{idx}")
    logger.info("Launching...")
    api: ObjectAPI = ClusterAPI()
    if idx % 2 != 0:
        api = JobAPI(namespace='')
    informer = Informer(api)

    def add_callback_fn(_):
        with LOCK:
            global UPDATE_COUNTER  # pylint: disable=global-statement
            UPDATE_COUNTER += 1
            logger.info("ADD: %d", UPDATE_COUNTER)

    def update_callback_fn(_, __):
        with LOCK:
            global UPDATE_COUNTER  # pylint: disable=global-statement
            UPDATE_COUNTER += 1
            logger.info("UPDATE: %d", UPDATE_COUNTER)

    def delete_callback_fn(_):
        with LOCK:
            global UPDATE_COUNTER  # pylint: disable=global-statement
            UPDATE_COUNTER += 1
            logger.info("DELETE: %d", UPDATE_COUNTER)

    informer.add_event_callbacks(add_event_callback=add_callback_fn,
                                 update_event_callback=update_callback_fn,
                                 delete_event_callback=delete_callback_fn)
    informer.start()


def launch_parallel_informers(num_informers: int = 256):
    """Main function to launch informers and perform cluster and job operations."""
    # For 1 worker, scales up to 512 informers (haven't tested further).
    global UPDATE_COUNTER  # pylint: disable=global-statement
    for i in range(num_informers):
        thread = threading.Thread(target=launch_informer, args=(i, ))
        thread.start()
    time.sleep(3)
    cluster_api = ClusterAPI()
    try:
        UPDATE_COUNTER = 0
        cluster_api.delete('hi')
    except APIException:
        pass

    job_api = JobAPI(namespace='default')
    try:
        job_api.delete('hi')
    except APIException:
        pass

    # Create cluster
    cluster_dict = {
        'kind': 'Cluster',
        'metadata': {
            'name': 'hi',
        },
        'spec': {
            'manager': 'k8',
        }
    }
    UPDATE_COUNTER = 0
    cluster_api.create(cluster_dict)

    # Create job
    job_dict = {
        'kind': 'Job',
        'metadata': {
            'name': 'hi',
            'namespace': 'default',
        },
        'spec': {
            'run': 'echo hello'
        }
    }
    job_api.create(job_dict)

    # Update cluster in a loop
    while True:
        UPDATE_COUNTER = 0
        try:
            cluster_obj = cluster_api.get('hi')
            cluster_obj.status.allocatable_capacity = {}
            cluster_obj.status.capacity = {}
            cluster_api.update(cluster_obj.model_dump(mode="json"))
        except APIException:
            pass

        try:
            job_obj = job_api.get('hi')
            job_obj.metadata.labels = {'test': 'test'}
            job_api.update(job_obj.model_dump(mode="json"))
        except APIException:
            pass

        time.sleep(3)
        print("\n\n\n\n\n")


if __name__ == "__main__":
    launch_parallel_informers()
