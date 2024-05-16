from concurrent.futures import ThreadPoolExecutor, as_completed
import subprocess
import time
import uuid
from kubernetes import client, config
from kubernetes.watch import Watch
import datetime
import numpy as np
import pandas as pd
import pytz
from kubernetes.client import V1DeleteOptions

# Load the kube config from the default location
config.load_kube_config()

v1 = client.CoreV1Api()

def submit_job_to_skyctl(job_name):
    command = [
        'skyctl', 'create', 'job', job_name, '--replicas', '1',
        '--run', 'taskset -c 1 ./run -a run -S parsec -p blackscholes -i native -n 1',
        '--cpus', '0.01', '--labels', 'app','iperf3',
        '--image', 'anakli/cca:parsec_blackscholes', '--restart_policy', 'Never'
    ]
    subprocess.run(command, check=True)

def watch_job_scheduling(job_name, submission_time):
    w = Watch()
    try:
        for event in w.stream(v1.list_namespaced_event, namespace='default', timeout_seconds=600):
            # Extract event details correctly
            event_object = event['object']
            involved_object = event_object.involved_object
            event_reason = event_object.reason
            last_timestamp = event_object.last_timestamp
            
            # Debugging output: print every event's important details
            print(f"Event: {event_reason} for {involved_object.name} at {last_timestamp}")

            # Check if the event is related to the job and has the reason 'Scheduled'
            if involved_object.name.startswith(job_name) and event_reason == 'Scheduled':
                # Ensure timezone-aware comparison
                if last_timestamp.tzinfo is None:
                    last_timestamp = pytz.utc.localize(last_timestamp)

                delay = (last_timestamp - submission_time).total_seconds()
                print(f"Job {job_name} scheduled at {last_timestamp} (Scheduling Delay: {delay} seconds)")
                w.stop()
                return delay
    finally:
        w.stop()  # Ensure the watch is stopped after processing

def delete_job_via_skyctl(job_name):
    command = ['skyctl', 'delete', 'job', job_name]
    subprocess.run(command, check=True)

def find_and_delete_pod(base_name, namespace='default'):
    pods = v1.list_namespaced_pod(namespace)
    for pod in pods.items:
        if pod.metadata.name.startswith(base_name):
            delete_options = V1DeleteOptions(grace_period_seconds=0)
            v1.delete_namespaced_pod(name=pod.metadata.name, namespace=namespace, body=delete_options)
            break

def submit_and_watch_job(job_name, submission_time):
    try:
        submit_job_to_skyctl(job_name)
        delay = watch_job_scheduling(job_name, submission_time)
        delete_job_via_skyctl(job_name)
        time.sleep(0.5)  # Wait for the pod to be deleted
        find_and_delete_pod(job_name)
        return delay
    except Exception as e:
        print(f"Error with job {job_name}: {str(e)}")
        return None

def measure_scheduling_times(job_counts):
    timezone = pytz.timezone('UTC')
    results = []

    for count in job_counts:
        with ThreadPoolExecutor(max_workers=count) as executor:
            future_to_job = {executor.submit(submit_and_watch_job, uuid.uuid4().hex, datetime.datetime.now(timezone)): i for i in range(count)}
            delays = [future.result() for future in as_completed(future_to_job)]
            delays = [d for d in delays if d is not None]  # Filter out failed or None results

            if delays:
                average_delay = np.mean(delays)
                p95_delay = np.percentile(delays, 95)
                p99_delay = np.percentile(delays, 99)
                results.append({'Job Count': count, 'Average Delay': average_delay, '95th Percentile': p95_delay, '99th Percentile': p99_delay})
                print(f"Results for {count} jobs: Avg Delay={average_delay}s, 95th Percentile={p95_delay}s, 99th Percentile={p99_delay}s")

    # Convert results to DataFrame and save to CSV
    df = pd.DataFrame(results)
    df.to_csv('scheduling_delays_1_200_2_clusters.csv', index=False)
    print("Results saved to scheduling_delays.csv")

job_counts = [1, 2, 5, 10, 25, 50, 100]
measure_scheduling_times(job_counts)
