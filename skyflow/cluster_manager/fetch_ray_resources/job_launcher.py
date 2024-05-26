import json
import subprocess
import sys
from typing import Dict


def load_job_from_json(job_json: str) -> Dict:
    """
    Load the job object from its JSON representation.
    """
    return json.loads(job_json)


def run_docker_container(job: Dict):
    """
    Run the specified Docker container with the required parameters.
    """
    image = job['spec']['image']
    envs = job['spec']['envs']
    ports = job['spec']['ports']
    run_command = job['spec']['run']

    env_vars = ' '.join([f"-e {key}={value}" for key, value in envs.items()])
    port_mappings = ' '.join([f"-p {port}:{port}" for port in ports])

    command = f"docker run {env_vars} {port_mappings} {image} {run_command}"
    print(f"Running command: {command}")
    process = subprocess.Popen(command, shell=True)
    return process.wait()


def main(job_json: str):
    job = load_job_from_json(job_json)
    exit_code = run_docker_container(job)
    sys.exit(exit_code)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python run_docker_job.py '<job_json>'")
        sys.exit(1)

    job_json = sys.argv[1]
    main(job_json)
