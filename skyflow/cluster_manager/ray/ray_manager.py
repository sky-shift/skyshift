import json
import logging
import os
import tarfile
import time
from typing import Any, Dict, List, Optional
from uuid import uuid4

import paramiko
import ray
import regex as re 
from ray.job_submission import JobSubmissionClient
from ray.runtime_env import RuntimeEnv
from kubernetes import client, config

from skyflow import utils
from skyflow.cluster_manager.manager import Manager
from skyflow.globals import APP_NAME
from skyflow.templates import (ClusterStatus,
                               ClusterStatusEnum,
                               Job, ResourceEnum,
                               TaskStatusEnum)
from skyflow.templates.job_template import RestartPolicyEnum
from skyflow.templates.resource_template import ContainerEnum

# Import the new SSH utility functions and classes
from skyflow.utils.ssh_utils import (
    SSHParams, SSHStatusEnum, check_reachable, connect_ssh_client, ssh_send_command, SSHConnectionError
)

RAY_CLIENT_PORT = 10001
RAY_JOBS_PORT = 8265
RAY_NODES_PORT = 6379

RAY_JSON_PATTERN = "(\{(?:[^{}]|(?R))*\})"

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(name)s - %(asctime)s - %(levelname)s - %(message)s")

class RayManager(Manager):
    """ Compatibility layer for Ray cluster manager. """

    is_initialized = False

    def __init__(self, name: str, ssh_key_path: Optional[str], username: str,
                 host: str, logger: Optional[logging.Logger] = None):
        super().__init__(name)
        self.cluster_name = utils.sanitize_cluster_name(name)
        self.logger = logger if logger else logging.getLogger(f"[{name} - Ray Manager]")
        self.accelerator_types: Dict[str, str] = {}
        self.ssh_key_path = ssh_key_path
        self.username = username
        self.job_registry = {} # Maybe replace by updating status on ETCD 
        self.host = host
        self.ssh_params = SSHParams(
            remote_hostname=host,
            remote_username=username,
            rsa_key=ssh_key_path
        )
        self.ssh_client = connect_ssh_client(self.ssh_params).ssh_client
        self.remote_dir = os.path.join(self._get_remote_home_directory(), f".{APP_NAME}")
        self.client = self._connect_to_ray_cluster()
        if not self.client: # If the client is still not initialized, ray might not be installed
            self.logger.info("Ray client not initialized. Attempting to install Ray.")
            self._setup()

    def _setup(self):
        """
        Checks for available container managers and sets up the Ray cluster.
        """
        container_managers = self._find_available_container_managers()
        if not container_managers:
            self.logger.error("No supported container managers found.")
            raise EnvironmentError("No supported container managers found.")
        self._install_ray()
        self.client = self._connect_to_ray_cluster()

    def _connect_to_ray_cluster(self) -> JobSubmissionClient:
        """Connect to the Ray cluster using the Ray client."""
        try:
            #TODO: change to https
            return JobSubmissionClient(f"http://{self.host}:{RAY_JOBS_PORT}")
        except ConnectionError as error:
            self.logger.error(f"Failed to connect to the Job Submission Server: {error}")


    def _find_available_container_managers(self) -> list:
        """Check which container managers are installed and return a list of available managers."""
        available_containers = []
        for container in ContainerEnum:
            try:
                command = f"command -v {container.value.lower()}"
                output = ssh_send_command(self.ssh_client, command)
                if output:
                    available_containers.append(container)
                    self.logger.info(f"{container.value} is available.")
            except Exception as error:
                self.logger.error(f"Error checking for {container.value}: {error}")
        return available_containers

    def _copy_file_to_remote(self, local_path: str, remote_path: str):
        """Copy a file from the local system to the remote system."""
        #Check if folder exists
        command = f"mkdir -p {os.path.dirname(remote_path)}"
        ssh_send_command(self.ssh_client, command)
        with self.ssh_client.open_sftp() as sftp:
            sftp.put(local_path, remote_path)
            self.logger.info(f"Copied {local_path} to {remote_path} on the remote system.")

    def _create_archive(self, directory: str, archive_name: str):
        """Create a tar archive of the directory excluding ray_manager.py."""
        with tarfile.open(archive_name, "w:gz") as tar:
            for root, _, files in os.walk(directory):
                for file in files:
                    full_path = os.path.join(root, file)
                    tar.add(full_path, arcname=file)

    def _extract_archive_on_remote(self, remote_archive_path: str):
        """Extract the tar archive on the remote system."""
        self.logger.info(f"Extracting {remote_archive_path} on the remote system.")
        command = f"tar xzfv {remote_archive_path} -C {self.remote_dir}"
        stdout = ssh_send_command(self.ssh_client, command)
        self.logger.info(stdout)
        ssh_send_command(self.ssh_client, f"rm {remote_archive_path}")

    def _copy_required_files(self):
        """Copy the required files to the remote system."""
        local_directory = os.path.dirname(os.path.realpath(__file__))
        self.logger.info(f"Copying files from {local_directory} to the remote system.")
        archive_name = './ray_manager_files.tar.gz'

        remote_extract_path = self.remote_dir
        remote_archive_path = f'{remote_extract_path}/ray_manager_files.tar.gz'
        self.logger.info(f"Copying files to {remote_extract_path} on the remote system.")

        self._create_archive(os.path.join(local_directory, "remote"), archive_name)
        self._copy_file_to_remote(archive_name, remote_archive_path)
        self._extract_archive_on_remote(remote_archive_path)

        # Clean up local archive
        os.remove(archive_name)

    def _get_remote_home_directory(self):
        """Fetch the home directory of the remote user."""
        command = "echo $HOME"
        return ssh_send_command(self.ssh_client, command).strip()

    def _install_ray(self):
        """Set up Ray using Miniconda."""
        try:
            self._copy_required_files()
            self.logger.info("Copied required files to the remote system.")

            self.logger.info("Installing Miniconda & Ray...")
            install_conda_cmd = f"bash {self.remote_dir}/ray_install.sh"
            ssh_send_command(self.ssh_client, install_conda_cmd)
            self.logger.info("Ray successfully started.")
        except paramiko.SSHException as error:
            self.logger.error(f"Error setting up Ray: {error}")

    def close(self):
        """Closes the SSH connection."""
        self.ssh_client.close()

    def get_accelerator_types(self) -> Dict[str, str]:
        """
        Fetches accelerator types for each node in the Ray cluster.

        Returns:
            Dict[str, str]: A dictionary mapping node names to their accelerator types.
        """
        accelerator_types = {}
        self.logger.info("Fetching accelerator types for nodes.")
        try:
            available_resources = ray.available_resources()
            self.logger.info(available_resources)
            for resource, quantity in available_resources.items():
                if resource.startswith("GPU"):
                    node_name = resource.split(":")[0]  # Extract node name
                    accelerator_types[node_name] = f"{quantity} GPUs"

            self.logger.info("Fetched accelerator types for nodes.")
        except Exception as error:
            self.logger.error(f"Failed to fetch accelerator types: {error}")

        return accelerator_types

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

        except TimeoutError:
            logging.error("Ray API call timed out.")
            return ClusterStatus(
                status=ClusterStatusEnum.ERROR.value,
                capacity=self.cluster_resources,
                allocatable_capacity=self.allocatable_resources,
            )
        except RuntimeError as error:
            # Catch-all for any other exception, which likely indicates an ERROR state
            logging.error(f"Unexpected error: {error}")
            return ClusterStatus(
                status=ClusterStatusEnum.ERROR.value,
                capacity=self.cluster_resources,
                allocatable_capacity=self.allocatable_resources,
            )

    def _process_gpu_resources(
            self, resources: Dict[str,
                                  Dict[str,
                                       float]]) -> Dict[str, Dict[str, float]]:
        # Refetch node accelerator types if the nodes have changed
        # (such as in cluster autoscaling or admin adds/removes nodes).
        if not self.accelerator_types or not set(
                self.accelerator_types).issubset(set(resources.keys())):
            self.accelerator_types = self.get_accelerator_types()

        for node_name, accelerator_type in self.accelerator_types.items():
            gpu_value: float = resources[node_name].pop(ResourceEnum.GPU.value)
            resources[node_name][accelerator_type] = gpu_value
        return resources

    @property
    def cluster_resources(self):
        """
        Gets total cluster resources for each node using Ray,
        excluding the internal head node.
        """

        # Connect to the Ray cluster
        self.client = self._connect_to_ray_cluster()

        # Submit a job to fetch the cluster resources
        job_id = self.client.submit_job(
            entrypoint=f"python {self.remote_dir}/fetch_ray_resources.py"
        )

        # Wait for the job to finish and fetch the results
        job_info = self.client.get_job_info(job_id)
        while job_info.status != 'SUCCEEDED':
            job_info = self.client.get_job_info(job_id)

        # Fetch the job logs
        logs = self.client.get_job_logs(job_id)
        json_pattern = re.compile(RAY_JSON_PATTERN)
        match = json_pattern.search(logs)

        if match:
            try:
                cluster_resources = json.loads(match.group(0))
            except json.JSONDecodeError as e:
                self.logger.exception("Failed to decode JSON from the logs, check the log output for errors.", e)
                cluster_resources = {}
        else:
            self.logger.exception("No JSON object found in the logs.")
            cluster_resources = {}

        return cluster_resources

    @property
    def allocatable_resources(self):
        """
        Gets total cluster resources for each node using Ray,
        excluding the internal head node.
        """

        # Connect to the Ray cluster
        self.client = self._connect_to_ray_cluster()

        # Submit a job to fetch the cluster resources
        job_id = self.client.submit_job(
            entrypoint=f"python {self.remote_dir}/fetch_ray_allocatable_resources.py"
        )

        # Wait for the job to finish and fetch the results
        job_info = self.client.get_job_info(job_id)
        while job_info.status != 'SUCCEEDED':
            job_info = self.client.get_job_info(job_id)

        # Fetch the job logs
        logs = self.client.get_job_logs(job_id)
        json_pattern = re.compile(RAY_JSON_PATTERN)
        match = json_pattern.search(logs)

        if match:
            try:
                cluster_resources = json.loads(match.group(0))
            except json.JSONDecodeError as e:
                self.logger.exception("Failed to decode JSON from the logs, check the log output for errors.", e)
                cluster_resources = {}
        else:
            self.logger.exception("No JSON object found in the logs.")
            cluster_resources = {}

        return cluster_resources

    def submit_job(self, job: Job) -> Dict[str, Any]:
        """
        Submit a job to the Ray cluster using Docker containers. This method checks if the job has 
        already been submitted and if so, does nothing.

        Args:
            job: Job object containing job specifications, including Docker image.

        Returns:
            Dict[str, Any]: A dictionary containing job submission details.
        """
        self.client = self._connect_to_ray_cluster()
        # Generate a unique identifier for the job
        job_id = f"{job.get_name()}-{job.get_namespace()}-{uuid4().hex[:10]}"

        submission_details = {
            "manager_job_id": job_id,
        }

        # Check if the job has already been submitted
        if job.get_name() in self.job_registry:
            return submission_details

        # Serialize the job object to JSON
        job_json = json.dumps(job.model_dump())

        # Prepare the entrypoint for the job
        entrypoint = f"python {self.remote_dir}/job_launcher.py '{job_json}'"

        # Submit the job to the Ray cluster
        self.client.submit_job(
            entrypoint=entrypoint,
            submission_id=job_id,
            entrypoint_num_cpus=job.spec.resources.get(ResourceEnum.CPU.value, 0),
            entrypoint_num_gpus=job.spec.resources.get(ResourceEnum.GPU.value, 0),
            entrypoint_memory=int(job.spec.resources.get(ResourceEnum.MEMORY.value, 0)),
            entrypoint_resources={k: v for k, v in job.spec.resources.items()
                                  if k not in {ResourceEnum.CPU.value,
                                               ResourceEnum.GPU.value,
                                               ResourceEnum.MEMORY.value}}
        )

        # Store additional information about the job submission
        self.job_registry[job.get_name()] = job_id

        return submission_details

    def delete_job(self, job: Job) -> None:
        """
        Delete a job from the Ray cluster. This method stops the job and removes it from the job registry.

        Args:
            job: Job object containing job specifications.

        Returns:
            None
        """
        self.client = self._connect_to_ray_cluster()
        
        # Check if the job has been submitted
        job_id = job.status.job_ids[self.cluster_name]
        
        try:
            # Stop the job in the Ray cluster
            self.client.stop_job(job_id)
            self.logger.info(f"Successfully stopped job {job.get_name()} on the Ray cluster.")
            self.client.delete_job(job_id)
            self.logger.info(f"Successfully deleted job {job.get_name()} from the Ray cluster.")
        except Exception as e:
            self.logger.error(f"Failed to stop job {job_id}: {e}")
        
        # Remove the job from the registry
        del self.job_registry[job.get_name()]
        self.logger.info(f"Removed job {job.get_name()} from job registry.")
        

    def get_jobs_status(self) -> Dict[str, Dict[str, Dict[str, str]]]:
        """
        Gets the jobs tasks status. (Map from job name to task mapped to status)
        
        Returns:
            Dict[str, Dict[str, Dict[str, str]]]: A dictionary mapping job names to task statuses.
        """
        self.client = self._connect_to_ray_cluster()

        # Generate a unique identifier for the status fetching job
        job_id = f"fetch_status_{uuid4().hex[:10]}"

        # Submit the job to the Ray cluster
        self.client.submit_job(
            entrypoint=f"python {self.remote_dir}/fetch_job_status.py",
            submission_id=job_id
        )

        job_info = self.client.get_job_info(job_id)
        while job_info.status != 'SUCCEEDED':
            job_info = self.client.get_job_info(job_id)
        # Fetch the logs of the job to get the output

        logs = self.client.get_job_logs(job_id)
        json_pattern = re.compile(RAY_JSON_PATTERN)
        match = json_pattern.search(logs)
        if match:
            try:
                jobs_dict = json.loads(match.group(0))
            except json.JSONDecodeError as e:
                logging.error("Failed to decode JSON from the logs, check the log output for errors.", e)
                jobs_dict = {}
        else:
            logging.error("No JSON object found in the logs.")
            jobs_dict = {}

        return jobs_dict

    def get_job_logs(self, job: Job) -> List[str]:
            """
            Gets logs for a given job.
            
            Args:
                job: Job object containing job specifications.

            Returns:
                List[str]: A list of logs for the job.
            """
            self.client = self._connect_to_ray_cluster()
            job_id = job.status.job_ids[self.cluster_name]
            self.logger.info(f"Fetching logs for job {job_id} on the Ray cluster.")
            logs = []
            try:
                # Get logs for the job from the Ray cluster
                log = self.client.get_job_logs(job_id)
                logs.append(log)
                self.logger.info(f"Fetched logs for job {job_id} on the Ray cluster.")
            except Exception as e:
                self.logger.error(f"Failed to fetch logs for job {job_id}: {e}")
            
            return logs
    
#print("Ray Manager")
rm = RayManager("ray", "/home/alex/Documents/skyflow/slurm/slurm", "alex", "35.232.174.39")
#print(rm.cluster_resources)
#print(rm.allocatable_resources)
#rm = RayManager("ray", "{self.remote_dir}/Documents/skyflow/slurm/slurm", "alex", "35.192.204.253")
#print(rm.get_cluster_status())

# Create a Job instance
#job = Job()
#job.metadata.name = "testjob"
#job.spec.image = "anakli/cca:parsec_blackscholes"
#job.spec.resources = {
#    ResourceEnum.CPU.value: 1,
#    ResourceEnum.MEMORY.value: 512  # In MB
#}
#job.spec.run = "ls -la && taskset -c 1 ./run -a run -S parsec -p blackscholes -i native -n 1"
#job.spec.envs = {"ENV_VAR": "value"}
#job.spec.ports = [8080]
#job.spec.replicas = 1
#job.spec.restart_policy = RestartPolicyEnum.NEVER.value

