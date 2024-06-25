"""
Utility functions for the Ray cluster manager.
"""

import logging
import os
import tarfile
from typing import Any, Dict, List

import paramiko
from paramiko import SSHClient
from ray.job_submission import JobDetails

from skyshift.templates.resource_template import CRIEnum, ResourceEnum
from skyshift.utils.ssh_utils import ssh_send_command


def create_archive(directory: str, archive_name: str):
    """Create a tar archive of the directory excluding ray_manager.py."""
    with tarfile.open(archive_name, "w:gz") as tar:
        for root, _, files in os.walk(directory):
            for file in files:
                full_path = os.path.join(root, file)
                tar.add(full_path, arcname=file)


def copy_file_to_remote(ssh_client: SSHClient, local_path: str,
                        remote_path: str):
    """Copy a file from the local system to the remote system."""
    #Check if folder exists
    command = f"mkdir -p {os.path.dirname(remote_path)}"
    ssh_send_command(ssh_client, command)
    with ssh_client.open_sftp() as sftp:
        sftp.put(local_path, remote_path)


def extract_archive_on_remote(ssh_client: SSHClient, remote_dir: str,
                              remote_archive_path: str):
    """Extract the tar archive on the remote system."""
    command = f"tar xzfv {remote_archive_path} -C {remote_dir} \
        && rm -f {remote_archive_path}"

    ssh_send_command(ssh_client, command)


def process_cluster_status(status_dict: Dict[str, Any],
                           usage: bool) -> Dict[str, Dict[str, float]]:
    """
    Processes the cluster status and extracts resource usage or capacity information.

    Args:
        status_dict (Dict[str, Any]): The status dictionary containing \
            cluster status information.
        usage (bool): A boolean indicating whether to process usage (True) \
            or capacity (False) data.

    Returns:
        Dict[str, Dict[str, float]]: A dictionary where the keys are node IDs \
            and the values are dictionaries with resource names as keys and their \
            corresponding quantities as values.
    """
    result: Dict[str, Dict[str, float]] = {}

    info = status_dict.get("data", {}).get("clusterStatus",
                                           {}).get("loadMetricsReport",
                                                   {}).get("usageByNode",
                                                           {}).items()
    for node_id, resources in info:
        if result.get(node_id) is None:
            res = {}
        for resource_name, quant_list in resources.items():
            quantity = quant_list[1] - quant_list[0] if usage else quant_list[1]
            if "objectStoreMemory" in resource_name:
                #Disk resources are fetched as bytes, convert to MB
                res[ResourceEnum.DISK.value] = quantity / (1024**2)
            elif "CPU" in resource_name.upper():
                res[ResourceEnum.CPU.value] = quantity
            elif "memory" in resource_name.lower():
                # Memory resources are fetched as bytes, convert to MB
                res[ResourceEnum.MEMORY.value] = quantity / (1024**2)
            elif "accelerator_type" in resource_name:
                gpu_type = resource_name.split(":")[1]
                res[gpu_type] = quantity
            elif "GPU" in resource_name.upper():
                res[ResourceEnum.GPU.value] = quantity
        result[node_id] = res

    return result


def extract_job_name(submission_id: str) -> str:
    """
    Extracts the original job name from the submission_id.
    """
    parts = submission_id.rsplit('-', 2)
    return '-'.join(parts[:-2]) if len(parts) >= 3 else submission_id


def map_ray_status_to_task_status(ray_status: str) -> str:
    """
    Maps Ray job statuses to SkyShift's statuses.
    """
    status_mapping = {
        "PENDING": "PENDING",
        "RUNNING": "RUNNING",
        "SUCCEEDED": "COMPLETED",
        "FAILED": "FAILED",
        "STOPPED": "DELETED",  # Assuming STOPPED is treated as FAILED
    }
    return status_mapping.get(ray_status, "UNKNOWN")


def fetch_all_job_statuses(
        jobs_details: List[JobDetails]
) -> Dict[str, Dict[str, Dict[str, str]]]:
    """
    Processes the status of all jobs from the Ray cluster.
    """
    jobs_dict: Dict[str, Dict[str, Dict[str, str]]] = {
        "tasks": {},
        "containers": {}
    }

    for job in jobs_details:
        #Only keep track of jobs deployed by SkyShift
        if not job.submission_id or len(job.submission_id.split('-')) != 3:
            # Doesn't follow the SkyShift format
            continue
        job_name = extract_job_name(job.submission_id)

        job_status = map_ray_status_to_task_status(job.status)

        if job_name not in jobs_dict["tasks"]:
            jobs_dict["tasks"][job_name] = {}
            jobs_dict["containers"][job_name] = {}

        # Assuming all tasks are in the same container for simplicity
        jobs_dict["tasks"][job_name][job_name] = job_status
        jobs_dict["containers"][job_name][job_name] = job_status

    return jobs_dict


def copy_required_files(ssh_client: paramiko.SSHClient, remote_dir: str,
                        logger: logging.Logger):
    """Copy the required files to the remote system."""
    local_directory = os.path.dirname(os.path.realpath(__file__))
    logger.info(f"Copying files from {local_directory} to the remote system.")
    archive_name = './ray_manager_files.tar.gz'

    remote_extract_path = remote_dir
    remote_archive_path = f'{remote_extract_path}/ray_manager_files.tar.gz'
    logger.info(
        f"Copying files to {remote_extract_path} on the remote system.")

    create_archive(os.path.join(local_directory, "remote"), archive_name)
    copy_file_to_remote(ssh_client, archive_name, remote_archive_path)
    extract_archive_on_remote(ssh_client, remote_dir, remote_archive_path)

    # Clean up local archive
    os.remove(archive_name)


def find_available_container_managers(ssh_client: paramiko.SSHClient,
                                      logger: logging.Logger) -> list:
    """Check which container managers are installed and return a list of available managers."""
    available_containers = []
    for container in CRIEnum:
        try:
            command = f"command -v {container.value.lower()}"
            output, _ = ssh_send_command(ssh_client, command)
            if output:
                available_containers.append(container)
                logger.info(f"{container.value} is available.")
        except paramiko.SSHException as error:
            logger.error(f"Error checking for {container.value}: {error}")
    return available_containers


def get_remote_home_directory(ssh_client: paramiko.SSHClient):
    """Fetch the home directory of the remote user."""
    command = "echo $HOME"
    output, _ = ssh_send_command(ssh_client, command)
    return output.strip()
