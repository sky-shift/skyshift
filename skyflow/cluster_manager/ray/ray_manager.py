"""
Represents the comptability layer over Ray native API.
"""
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
from skyflow.templates import (ClusterStatus,
                               ClusterStatusEnum,
                               Job, ResourceEnum,
                               TaskStatusEnum)
from skyflow.templates.job_template import RestartPolicyEnum
from skyflow.templates.resource_template import ContainerEnum

RAY_CLIENT_PORT = 10001
RAY_JOBS_PORT = 8265
RAY_NODES_PORT = 6379

RAY_JSON_PATTERN = "(\{(?:[^{}]|(?R))*\})"

client.rest.logger.setLevel(logging.WARNING)
logging.basicConfig(
    level=logging.INFO,
    format="%(name)s - %(asctime)s - %(levelname)s - %(message)s")


def process_pod_status(pod: client.V1Pod) -> str:
    """Processes pod status."""
    pod_status = pod.status.phase
    if pod_status == "Pending":
        if pod.spec.node_name is None:
            status = TaskStatusEnum.INIT.value
        else:
            status = TaskStatusEnum.PENDING.value
    elif pod_status == "Running":
        status = TaskStatusEnum.RUNNING.value
    elif pod_status == "Succeeded":
        status = TaskStatusEnum.COMPLETED.value
    elif pod_status in ["Failed", "Unknown"]:
        status = TaskStatusEnum.FAILED.value
    else:
        raise ValueError(f"Unknown pod status {pod_status}")
    return status

class RayConnectionError(config.config_exception.ConfigException):
    """Raised when there is an error connecting to the Kubernetes cluster."""


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
        self.accelerator_types: Dict[str, str] = {}
        self.host = host
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._setup_ssh_client()
        self.remote_dir = self._get_remote_home_directory()
        self.client = self._connect_to_ray_cluster()
        if not self.client: # If the client is still not initialized, ray might not be installed
            self.logger.info("Ray client not initialized. Attempting to install Ray.")
            self._setup_ray()
            self.client = self._connect_to_ray_cluster()

    def _connect_to_ray_cluster(self):
        """Connect to the Ray cluster using the Ray client."""
        client = None
        try:
            #TODO: change to https
            client = JobSubmissionClient(f"http://{self.host}:{RAY_JOBS_PORT}")
        except Exception as error:
            self.logger.error(f"Failed to connect to the Job Submission Server: {error}")
        return client

    def _setup_ssh_client(self):
        """Reads the SSH key file, and setups the SSH client."""
        try:
            key_file_path = os.path.abspath(os.path.expanduser(self.ssh_key_path))
            if not key_file_path:
                raise FileNotFoundError(f"SSH key file not found: {self.ssh_key_path}")

            private_key = paramiko.RSAKey.from_private_key_file(key_file_path)
            self.ssh_client.connect(hostname=self.host, username=self.username, pkey=private_key)
        except (IOError, paramiko.ssh_exception.SSHException) as e:
            self.logger.error(f"SSH connection setup failed: {e}")
            raise e

    def _find_available_container_manager(self):
        """Check which container managers are installed and return the first available."""
        available_containers = []
        for container in ContainerEnum:
            command = f"command -v {container.value.lower()}"
            _, stdout, _ = self.ssh_client.exec_command(command)
            if stdout.read():
                available_containers.append(container)
                self.logger.info(f"{container.value} is available.")
        
        if not available_containers:
            self.logger.error("No supported container managers found.")
            raise EnvironmentError("No supported container managers found.")
        
        return available_containers  # Return the first available container manager

    def _copy_file_to_remote(self, local_path: str, remote_path: str):
        """Copy a file from the local system to the remote system."""
        sftp = self.ssh_client.open_sftp()
        sftp.put(local_path, remote_path)
        sftp.close()

    def _create_archive(self, directory: str, archive_name: str):
        """Create a tar archive of the directory excluding ray_manager.py."""
        with tarfile.open(archive_name, "w:gz") as tar:
            tar.add(directory, arcname=os.path.basename(directory), 
                    filter=lambda x: None if x.name.endswith('ray_manager.py') else x)


    def _extract_archive_on_remote(self, remote_archive_path: str, remote_extract_path: str):
        """Extract the tar archive on the remote system."""
        command = f"tar -xzf {remote_archive_path} -C {remote_extract_path}"
        _, stdout, stderr = self.ssh_client.exec_command(command)
        stdout.channel.recv_exit_status()
        self.logger.info(stdout.read().decode())
        self.logger.error(stderr.read().decode())

    def _copy_required_files(self):
        """Copy the required files to the remote system."""
        local_directory = os.path.dirname(os.path.realpath(__file__))
        self.logger.info(f"Copying files from {local_directory} to the remote system.")
        archive_name = 'ray_manager_files.tar.gz'

        remote_extract_path = self.remote_dir
        remote_archive_path = f'{remote_extract_path}/ray_manager_files.tar.gz'

        self._create_archive(local_directory, archive_name)
        self._copy_file_to_remote(archive_name, remote_archive_path)
        self._extract_archive_on_remote(remote_archive_path, remote_extract_path)

        # Clean up local archive
        os.remove(archive_name)

    def _get_remote_system_memory(self):
        """Get the memory of the remote system in GB."""
        _, stdout, _ = self.ssh_client.exec_command("free -g | awk '/^Mem:/ {print $2}'")
        return int(stdout.read().strip())

    def _detect_shell(self):
        """Detect the shell used by the remote system."""
        _, stdout, _ = self.ssh_client.exec_command("echo $SHELL")
        shell = stdout.read().decode().strip().split('/')[-1]
        return shell

    def _restart_ssh_connection(self):
        """Restart the SSH connection."""
        self.ssh_client.close()
        self._setup_ssh_client()

    def _get_remote_home_directory(self):
        """Fetch the home directory of the remote user."""
        _, stdout, _ = self.ssh_client.exec_command("echo $HOME")
        home_directory = stdout.read().strip().decode('utf-8')
        return home_directory

    def _setup_ray(self):
        """Set up Ray using Miniconda."""

        if self.is_initialized:
            self.logger.info("Ray is already initialized.")
            return
        self.is_initialized = True

        try:
            self._copy_required_files()
            self.logger.info("Copied required files to the remote system.")

            # Detect the shell and source the appropriate profile
            shell = self._detect_shell()
            if shell == 'zsh':
                profile_cmd = "source ~/.zshrc"
            elif shell == 'ksh':
                profile_cmd = "source ~/.kshrc"
            else:
                profile_cmd = "source ~/.bashrc"  # Default to bashrc if unknown

            # Install Miniconda
            self.logger.info("Installing Miniconda...")
            install_conda_cmd = f"bash ~/miniconda_install.sh && {profile_cmd}"
            _, stdout, stderr = self.ssh_client.exec_command(install_conda_cmd)
            stdout.channel.recv_exit_status()
            self.logger.info(stdout.read().decode())
            self.logger.error(stderr.read().decode())

            # Restart SSH connection
            self.logger.info("Restarting SSH connection...")
            self._restart_ssh_connection()

            # Include the explicit path to the conda binary
            conda_path = f"{self.remote_dir}/miniconda/bin/conda"
            if shell == 'zsh':
                conda_profile_cmd = f"export PATH={self.remote_dir}/miniconda/bin/conda:$PATH && source ~/.zshrc"
            elif shell == 'ksh':
                conda_profile_cmd = f"export PATH={self.remote_dir}/miniconda/bin/conda:$PATH && source ~/.kshrc"
            else:
                conda_profile_cmd = f"export PATH={self.remote_dir}/miniconda/bin/conda:$PATH && source ~/.bashrc"

            # Create conda environment and install Ray
            self.logger.info("Setting up Ray environment...")
            setup_cmd = f"{conda_profile_cmd} && {conda_path} create -n my_ray_env python=3.10 -y \
                && {conda_path} run -n my_ray_env pip install ray[all]"
            _, stdout, stderr = self.ssh_client.exec_command(setup_cmd)
            stdout.channel.recv_exit_status()
            self.logger.info(stdout.read().decode())
            self.logger.error(stderr.read().decode())

            remote_memory_gb = self._get_remote_system_memory()  # Get remote memory in GB
            recommended_shm_size = int(remote_memory_gb * 0.3 * 1024 * 1024 * 1024)  # in bytes

            # Start Ray in the new conda environment
            start_ray_cmd = f"""
                {conda_profile_cmd} && \
                {conda_path} run -n my_ray_env ray start --head --port={RAY_NODES_PORT} --dashboard-host=0.0.0.0 --object-store-memory={recommended_shm_size}
            """
            _, stdout, stderr = self.ssh_client.exec_command(start_ray_cmd)
            stdout.channel.recv_exit_status()
            self.logger.info(stdout.read().decode())
            self.logger.error(stderr.read().decode())

            self.logger.info("Ray successfully started.")
        except Exception as error:  # pylint: disable=broad-except
            self.logger.error(f"Error setting up Ray: {error}")

    def _check_ray_connection(self):
        """Attempt to initialize the Ray client, to check if it is reachable"""
        try:
            # Attempt to connect to the Ray cluster at the given host
            if ray.is_initialized():
                return True
        except Exception as error:
            self.logger.error(f"Failed to connect to Ray at {self.host}: {error}")
        return False

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
        except Exception as error:  # pylint: disable=broad-except
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
#rm = RayManager("ray", "{self.remote_dir}/Documents/skyflow/slurm/slurm", "alex", "34.30.51.77")
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

# Submit the Job
#rm.submit_job(job)
#time.sleep(5)
#print(rm.get_jobs_status())
#print(rm.get_job_logs(job))

#runtime_env = RuntimeEnv(
#    container={
#        "image": "rayproject/ray:latest-cpu"
#    }
#)
#
#client = JobSubmissionClient(os.environ.get("RAY_ADDRESS", "http://34.30.51.77:8265"))
#job_id = client.submit_job(
#    entrypoint="python batch_inference", runtime_env=runtime_env
#)
#print(job_id)