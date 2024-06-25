"""
Job launcher script to run a container job from a JSON specification.
The script mounts the required GCS buckets to the local system and  \
runs the Docker container with the specified parameters.
Designed for usage in Ray clusters.
"""
import argparse
import json
import os
import subprocess
import sys
from typing import Dict


def check_nvidia_smi() -> bool:
    """
    Check if nvidia-smi is available on the system.
    """
    try:
        subprocess.run(['nvidia-smi'],
                       stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE,
                       check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


# Assumes gcsfuse and fuse are installed on the system
def mount_bucket(bucket_name: str, local_mapping: str) -> None:
    """
    Mount the GCS bucket using gcsfuse.
    """
    command = f"gcsfuse -o allow_other {bucket_name} {local_mapping} > /dev/null 2>&1"
    try:
        subprocess.run(command, shell=True, check=True)
        print(f"Mounted bucket {bucket_name} to {local_mapping}")
    except subprocess.CalledProcessError as error:
        print(f"Error mounting bucket: {error}")
        sys.exit(1)


def unmount_bucket(local_mapping: str) -> None:
    """
    Unmount the GCS bucket using fusermount.
    """
    command = f"fusermount -u {local_mapping} > /dev/null 2>&1"
    try:
        subprocess.run(command, shell=True, check=True)
        print(f"Unmounted bucket from {local_mapping}")
    except subprocess.CalledProcessError as error:
        print(f"Error unmounting bucket: {error}")
        sys.exit(1)


def run_docker_container(job_dict: Dict) -> int:  #pylint: disable=too-many-locals
    """
    Run the specified Docker container with the required parameters and output the logs.
    """
    image = job_dict['spec']['image']
    envs = job_dict['spec']['envs']
    ports = job_dict['spec']['ports']
    run_command = job_dict['spec']['run']
    volumes: dict = job_dict['spec']['volumes']

    env_vars = ' '.join([f"-e {key}={value}" for key, value in envs.items()])
    port_mappings = ' '.join([f"-p {port}:{port}" for port in ports])
    volume_mappings = ''

    for bucket_name, volume in volumes.items():
        local_dir = f"{os.environ['HOME']}/.skyshift/{bucket_name}"
        subprocess.run(f"mkdir -p {local_dir}", shell=True, check=True)
        volume_mappings += f" -v {local_dir}:{volume['container_dir']}"
        mount_bucket(bucket_name, local_dir)

    command = f"docker run {'--gpus all' if check_nvidia_smi() else ''} \
                {env_vars} \
                {port_mappings} \
                {volume_mappings} \
                {image} \
                {run_command} \
                "

    with subprocess.Popen(command,
                          shell=True,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          text=True) as process:
        # Print the output in real-time
        while True:
            output = process.stdout.readline() if process.stdout else None
            if output == "" and process.poll() is not None:
                break
            if output:
                print(output.strip())

    # Wait for the process to finish and get the exit code
    return_code = process.wait()

    # Print any remaining stderr output
    stderr_output = process.stderr.read().strip() if process.stderr else ""
    if stderr_output:
        print(stderr_output)

    # Exit the script with the same code as the Docker container
    if return_code != 0:
        print(f"Container exited with error code: {return_code}")

    for bucket_name, volume in volumes.items():
        local_dir = f"{os.environ['HOME']}/.skyshift/{bucket_name}"
        unmount_bucket(local_dir)

    return return_code


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Run a container job from a JSON specification.')
    parser.add_argument('job_json',
                        type=str,
                        help='The JSON string of the job specification.')

    args = parser.parse_args()

    try:
        job = json.loads(args.job_json)
    except json.JSONDecodeError as error:
        print(f"Invalid JSON format: {error}")
        sys.exit(1)

    sys.exit(run_docker_container(job))
