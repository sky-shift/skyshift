"""
Ray compatibility layer for SkyShift.
This module provides a compatibility layer for Ray cluster manager using as backbone
the Ray Job Submission Server.
https://docs.ray.io/en/latest/cluster/running-applications/job-submission/sdk.html
"""

import json
import logging
import os
import traceback
from typing import Any, Dict, List, Optional
from uuid import uuid4

import paramiko
import requests
from fastapi import WebSocket
from ray.job_submission import JobSubmissionClient

from skyshift import utils
from skyshift.cluster_manager.manager import Manager
from skyshift.cluster_manager.ray.ray_utils import (
    copy_required_files, fetch_all_job_statuses,
    find_available_container_managers, get_remote_home_directory,
    process_cluster_status)
from skyshift.globals import APP_NAME, CLUSTER_TIMEOUT
from skyshift.templates import (ClusterStatus, ClusterStatusEnum, Job,
                               ResourceEnum)
# Import the new SSH utility functions and classes
from skyshift.utils.ssh_utils import (SSHParams, SSHStatusEnum, SSHStruct,
                                     connect_ssh_client, ssh_send_command)
from skyshift.utils.utils import fuzzy_map_gpu

RAY_CLIENT_PORT = 10001
RAY_JOBS_PORT = 8265
RAY_DASHBOARD_PORT = 8265
RAY_NODES_PORT = 6379

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(name)s - %(asctime)s - %(levelname)s - %(message)s")


class RayConnectionError(RuntimeError):
    """Raised when there is an error connecting to the Ray cluster."""


class RayManager(Manager):  # pylint: disable=too-many-instance-attributes
    """ Compatibility layer for Ray cluster manager. """

    def __init__(  # pylint: disable=too-many-arguments
            self,
            name: str,
            access_config: Dict[str, str],
            logger: Optional[logging.Logger] = None):
        super().__init__(name)
        self.cluster_name = utils.sanitize_cluster_name(name)
        self.logger: logging.Logger = logger if logger else logging.getLogger(
            f"[{name} - Ray Manager]")
        self.accelerator_types: Dict[str, str] = {}
        self.ssh_key_path = access_config.get("ssh_key_path", "")
        self.username = access_config.get("username", "")
        self.host = access_config.get("host", "")
        self.ssh_params = SSHParams(remote_hostname=self.host,
                                    remote_username=self.username,
                                    rsa_key=self.ssh_key_path)
        ssh_client: SSHStruct = connect_ssh_client(self.ssh_params)

        if not ssh_client.ssh_client or ssh_client.status == SSHStatusEnum.NOT_REACHABLE:
            self.logger.error(
                "Failed to establish an SSH connection to the remote host.")
            return
        client = ssh_client.ssh_client
        self.remote_dir = os.path.join(get_remote_home_directory(client),
                                       f".{APP_NAME}")
        self.client = self._connect_to_ray_cluster()
        if not self.client:  # If the client is still not initialized, ray might not be installed
            self.logger.info(
                "Ray client not initialized. Attempting to install Ray.")
            self._setup(client)
            self.client = self._connect_to_ray_cluster()
            if not self.client:
                self.logger.error(
                    "Failed to initialize Ray client. Exiting...")
                raise RayConnectionError("Failed to initialize Ray client.")
        self.logger.info("Ray client initialized.")

    def _setup(self, ssh_client: paramiko.SSHClient):
        """
        Checks for available container managers and sets up the Ray cluster.
        """
        container_managers = find_available_container_managers(
            ssh_client, self.logger)
        if not container_managers:
            self.logger.error("No supported container managers found.")
            raise ValueError("No supported container managers found.")
        self._install_ray(ssh_client)

    def _connect_to_ray_cluster(self) -> Optional[JobSubmissionClient]:
        """Connect to the Ray cluster using the Ray client."""
        try:
            return JobSubmissionClient(f"http://{self.host}:{RAY_JOBS_PORT}")
        except ConnectionError as error:
            self.logger.error(
                "Failed to connect to the Job Submission Server: %s", error)
        return None

    def _install_ray(self, ssh_client: paramiko.SSHClient):
        """Set up Ray using Miniconda."""
        try:
            copy_required_files(ssh_client, self.remote_dir, self.logger)
            self.logger.info("Copied required files to the remote system.")

            self.logger.info("Installing Miniconda & Ray...")
            install_conda_cmd = f"bash {self.remote_dir}/ray_install.sh"
            _, stderr = ssh_send_command(ssh_client, install_conda_cmd)
            if stderr:
                self.logger.error("Error installing Miniconda & Ray: %s",
                                  stderr)
                raise RayConnectionError("Error installing Miniconda & Ray.")
            self.logger.info("Ray successfully started.")
        except paramiko.SSHException as error:
            self.logger.error("Error setting up Ray: %s", error)

    async def execute_command(  # pylint: disable=too-many-arguments
            self, websocket: WebSocket, task: str, container: str, tty: bool,
            command: List[str]):
        """
        Execute a command on the head node.

        Args:
            command: Command to be executed on the Ray cluster.

        Returns:
            str: Output of the command execution.
        """
        raise NotImplementedError(
            "execute_command is not implemented for Ray.")

    def get_cluster_status(self):
        """
        Returns the current status of a Ray cluster with a timeout on the list_node call.
        """
        try:
            # If successful, you can parse these resources and return a proper ClusterStatus
            return ClusterStatus(
                status=ClusterStatusEnum.READY.value,
                capacity=self.cluster_resources,
                allocatable_capacity=self.allocatable_resources,
            )

        except (TimeoutError, RuntimeError):
            traceback.print_exc()
            return ClusterStatus(
                status=ClusterStatusEnum.ERROR.value,
                capacity=self.cluster_resources,
                allocatable_capacity=self.allocatable_resources,
            )

    def fetch_resources_from_dashboard(
            self, usage: bool) -> Dict[str, Dict[str, float]]:
        """
        Fetches resources from the Ray dashboard.
        """
        response = requests.get(
            f"http://{self.host}:{RAY_DASHBOARD_PORT}/api/cluster_status",
            timeout=CLUSTER_TIMEOUT)
        if response.status_code == 200:
            cluster_status = response.json()
            return process_cluster_status(cluster_status, usage)
        self.logger.error(
            "Failed to fetch resources from the Ray dashboard: %s",
            response.text)
        raise RayConnectionError(
            f"Failed to fetch resources from the Ray dashboard: {response.text}"
        )

    @property
    def cluster_resources(self):
        """
        Gets total cluster resources for each node using Ray, excluding the internal head node.
        """
        resources = self.fetch_resources_from_dashboard(usage=False)
        logging.debug("Cluster resources: %s", resources)
        return fuzzy_map_gpu(resources)

    @property
    def allocatable_resources(self):
        """
        Gets total allocatable resources for each node using Ray, excluding the internal head node.
        """
        resources = self.fetch_resources_from_dashboard(usage=False)
        logging.debug("Cluster available resources: %s", resources)
        return fuzzy_map_gpu(resources)

    def get_jobs_status(self) -> Dict[str, Dict[str, Dict[str, str]]]:
        """
        Gets the jobs tasks status. (Map from job name to task mapped to status)

        Returns:
            Dict[str, Dict[str, Dict[str, str]]]: A dictionary mapping job names to task statuses.
        """
        if not self.client:
            self.logger.error("Ray client not initialized.")
            raise RayConnectionError("Ray client not initialized.")

        jobs_details = self.client.list_jobs()
        status = fetch_all_job_statuses(jobs_details)
        self.logger.debug("Jobs status: %s", status)
        return status

    def get_job_logs(self, job) -> List[str]:
        """
        Gets logs for a given job.

        Args:
            job: Job object containing job specifications.

        Returns:
            List[str]: A list of logs for the job.
        """

        if not self.client:
            raise RayConnectionError("Ray client not initialized.")

        job_id = job.status.job_ids[self.cluster_name]
        self.logger.info("Fetching logs for job %s on the Ray cluster.",
                         job_id)
        logs = []
        try:
            log = self.client.get_job_logs(job_id)
            logs.append(log)
            self.logger.info("Fetched logs for job %s on the Ray cluster.",
                             job_id)
        except RuntimeError as error:
            self.logger.error("Failed to fetch logs for job %s: %s", job_id,
                              error)

        try:
            self.client.stop_job(job_id)
            self.client.delete_job(job_id)
        except RuntimeError as error:
            self.logger.error("Failed to stop job %s: %s", job_id, error)

        return logs

    def submit_job(self, job: Job) -> Dict[str, Any]:
        """
        Submit a job to the Ray cluster using Docker containers. This method checks if the job has
        already been submitted and if so, does nothing.

        Args:
            job: Job object containing job specifications, including Docker image.

        Returns:
            Dict[str, Any]: A dictionary containing job submission details.
        """
        # Generate a unique identifier for the job

        if not self.client:
            self.logger.error("Ray client not initialized.")
            return {}

        job_id = f"{job.get_name()}-{job.get_namespace()}-{uuid4().hex[:10]}"

        submission_details = {
            "manager_job_id": job_id,
        }

        # Serialize the job object to JSON
        job_json = json.dumps(job.model_dump())

        # Prepare the entrypoint for the job
        entrypoint = f"python {self.remote_dir}/job_launcher.py '{job_json}'"

        # Submit the job to the Ray cluster
        self.client.submit_job(
            entrypoint=entrypoint,
            submission_id=job_id,
            entrypoint_num_cpus=job.spec.resources.get(ResourceEnum.CPU.value,
                                                       0),
            entrypoint_num_gpus=job.spec.resources.get(ResourceEnum.GPU.value,
                                                       0),
            entrypoint_memory=int(
                job.spec.resources.get(ResourceEnum.MEMORY.value, 0)),
            entrypoint_resources={
                k: v
                for k, v in job.spec.resources.items() if k not in {
                    ResourceEnum.CPU.value, ResourceEnum.GPU.value,
                    ResourceEnum.MEMORY.value
                }
            })

        return submission_details

    def delete_job(self, job: Job) -> None:
        """
        Delete a job from the Ray cluster. This method stops the job and removes it from the job registry.

        Args:
            job: Job object containing job specifications.

        Returns:
            None
        """

        if not self.client:
            self.logger.error("Ray client not initialized.")
            return

        # Check if the job has been submitted
        job_id = job.status.job_ids[self.cluster_name]

        try:
            # Stop the job in the Ray cluster
            self.client.stop_job(job_id)
            self.logger.info("Successfully stopped job %s on the Ray cluster.",
                             job.get_name())
            self.client.delete_job(job_id)
            self.logger.info(
                "Successfully deleted job %s from the Ray cluster.",
                job.get_name())
        except RuntimeError as error:
            self.logger.error("Failed to stop job %s: %s", job_id, error)

        self.logger.info("Removed job from job registry: %s", job.get_name())

