import argparse
import json
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


def run_docker_container(job: Dict) -> int:
    """
    Run the specified Docker container with the required parameters and output the logs.
    """
    image = job['spec']['image']
    envs = job['spec']['envs']
    ports = job['spec']['ports']
    run_command = job['spec']['run']

    env_vars = ' '.join([f"-e {key}={value}" for key, value in envs.items()])
    port_mappings = ' '.join([f"-p {port}:{port}" for port in ports])

    command = f"""docker run {'--gpus all' if check_nvidia_smi() else ''} \
                {env_vars} \
                {port_mappings} \
                {image} \
                {run_command}
                """
    print(f"Running command: {command}")

    process = subprocess.Popen(command,
                               shell=True,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               text=True)

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
    except json.JSONDecodeError as e:
        print(f"Invalid JSON format: {e}")
        sys.exit(1)

    exit_code = run_docker_container(job)
    sys.exit(exit_code)