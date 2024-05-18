"""
Represents the comptability layer over Ray native API.
"""
import json
import logging
import os
from typing import Any, Dict, List, Optional

import paramiko
import ray
from ray.job_submission import JobSubmissionClient
from kubernetes import client, config

from skyflow import utils
from skyflow.cluster_manager.manager import Manager
from skyflow.templates import (ClusterStatus,
                               ClusterStatusEnum,
                               Job, ResourceEnum,
                               TaskStatusEnum)
from skyflow.templates.resource_template import ContainerEnum

RAY_CLIENT_PORT = 10001
RAY_JOBS_PORT = 8265
RAY_NODES_PORT = 6379

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
        self.client = self._connect_to_ray_cluster()
        if not self.client: # If the client is still not initialized, ray might not be installed
            self.logger.info("Ray client not initialized. Attempting to install Ray.")
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self._setup_ssh_client()
            self._install_ray()
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
            if not os.path.exists(os.path.abspath(os.path.expanduser(self.ssh_key_path))):
                raise FileNotFoundError(f"SSH key file not found: {self.ssh_key_path}")

            with open(os.path.abspath(os.path.expanduser(self.ssh_key_path)), "r") as key_file:
                private_key = paramiko.RSAKey.from_private_key(key_file)
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

    def _get_remote_system_memory(self):
        """Retrieve total memory available on the remote system in gigabytes."""
        command = "grep MemTotal /proc/meminfo | awk '{print $2}'"  # This command gets the memory in KB
        _, stdout, _ = self.ssh_client.exec_command(command)
        mem_kb = stdout.read().decode().strip()
        if mem_kb:
            return int(mem_kb) // 1024 // 1024  # Convert KB to GB
        else:
            self.logger.error("Failed to retrieve memory information from the remote system.")
            raise Exception("Failed to retrieve memory information from the remote system.")


    def _setup_containerized_ray(self, container_managers: List[ContainerEnum]):
        """Set up and start Ray within a chosen container environment."""

        try:
            remote_memory_gb = self._get_remote_system_memory()  # Get remote memory in GB
            # 30% of total memory for Ray's object store
            recommended_shm_size = f"{int(remote_memory_gb * 0.3)}G"
        except Exception as e:
            self.logger.error(f"Error calculating remote memory: {e}")
            return

        for container_manager in container_managers:
            self.logger.info(f"Setting up Ray using {container_manager.value}.")
            if container_manager == ContainerEnum.DOCKER:
                command = (
                    f"docker run -d -p {RAY_NODES_PORT}:{RAY_NODES_PORT} "
                    f"-p {RAY_JOBS_PORT}:{RAY_JOBS_PORT} "
                    f"-p {RAY_CLIENT_PORT}:{RAY_CLIENT_PORT} "
                    f"--shm-size={recommended_shm_size}gb "
                    "alexmontoril23/ray-manager:latest /bin/bash -c "
                    f"\"ray start --head --port={RAY_NODES_PORT} --dashboard-host=0.0.0.0; tail -f /dev/null\""
                )
            elif container_manager == ContainerEnum.PODMAN:
                command = (
                    f"podman run -d -p {RAY_NODES_PORT}:{RAY_NODES_PORT} "
                    f"-p {RAY_JOBS_PORT}:{RAY_JOBS_PORT} "
                    f"-p {RAY_CLIENT_PORT}:{RAY_CLIENT_PORT} "
                    f"--shm-size={recommended_shm_size}gb "
                    "alexmontoril23/ray-manager:latest /bin/bash -c "
                    f"\"ray start --head --port={RAY_NODES_PORT} --dashboard-host=0.0.0.0; tail -f /dev/null\""
                )
            elif container_manager == ContainerEnum.CONTAINERD:
                # Example command using containerd (assumes use of ctr)
                command = (
                    f"ctr run -d --net-host --memory {recommended_shm_size}G "
                    "alexmontoril23/ray-manager:latest ray "
                    f"/bin/bash -c \"ray start --head --port={RAY_NODES_PORT}; tail -f /dev/null\""
                )
            elif container_manager == ContainerEnum.SINGULARITY:
                # Singularity command to pull and run the specified Docker image
                command = (
                    f"singularity exec docker://alexmontoril23/ray-manager:latest "
                    f"/bin/bash -c \"ray start --head --port={RAY_NODES_PORT}; tail -f /dev/null\""
                )
            elif container_manager == ContainerEnum.PODMANHPC:
                # Customized command for Podman in HPC environments
                command = (
                    f"podman run -d --userns=keep-id -p {RAY_NODES_PORT}:{RAY_NODES_PORT} "
                    f"-p {RAY_JOBS_PORT}:{RAY_JOBS_PORT} "
                    f"-p {RAY_CLIENT_PORT}:{RAY_CLIENT_PORT} "
                    f"--shm-size={recommended_shm_size}gb "
                    "--security-opt label=disable "  # This might be necessary in some HPC environments
                    "alexmontoril23/ray-manager:latest /bin/bash -c "
                    f"\"ray start --head --port={RAY_NODES_PORT} --dashboard-host=0.0.0.0; tail -f /dev/null\""
                )
            else:
                self.logger.error(f"Unsupported container manager: {container_manager.value}")
                continue

            # Logging the command for debugging purposes
            self.logger.debug(f"Command for {container_manager.value}: {command}")

            _, _, stderr = self.ssh_client.exec_command(command)
            if stderr.read():
                error_msg = stderr.read().decode()
                self.logger.error(f"Failed to start Ray in {container_manager.value}: {error_msg} \
                                  Trying next container manager.")
                continue
            self.logger.info(f"Ray successfully started using {container_manager.value}.")

    def _check_ray_connection(self):
        """Attempt to initialize the Ray client, to check if it is reachable"""
        try:
            # Attempt to connect to the Ray cluster at the given host
            if ray.is_initialized():
                return True
        except Exception as error:
            self.logger.error(f"Failed to connect to Ray at {self.host}: {error}")
        return False

    def _install_ray(self):
        """Install Ray on the remote system."""
        self.logger.info("Ray is not installed or not reachable. Checking for container managers.")
        try:
            container_managers = self._find_available_container_manager()
            self._setup_containerized_ray(container_managers)  # Assuming it returns a single manager
            # Retry connecting to Ray after setup
            self.client = JobSubmissionClient(f"http://{self.host}:{RAY_JOBS_PORT}")
            self.logger.info("Successfully installed ray on the remote system.")
        except Exception as setup_error:
            self.logger.error(f"Failed to setup Ray: {setup_error}")

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
            entrypoint="python /fetch_ray_resources.py"
        )

        # Wait for the job to finish and fetch the results
        job_info = self.client.get_job_info(job_id)
        while job_info.status != 'SUCCEEDED':
            job_info = self.client.get_job_info(job_id)

        # Fetch the job logs
        logs = self.client.get_job_logs(job_id)

        print(logs)
        # Check if the last line is a valid JSON string
        try:
            cluster_resources = json.loads(logs)
        except json.JSONDecodeError as e:
            print("Failed to decode JSON from the logs, check the log output for errors.", e)
            cluster_resources = None

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
            entrypoint="python /fetch_ray_allocatable_resources.py"
        )

        # Wait for the job to finish and fetch the results
        job_info = self.client.get_job_info(job_id)
        while job_info.status != 'SUCCEEDED':
            job_info = self.client.get_job_info(job_id)

        # Fetch the job logs
        logs = self.client.get_job_logs(job_id)

        print(logs)
        # Check if the last line is a valid JSON string
        try:
            cluster_resources = json.loads(logs)
        except json.JSONDecodeError as e:
            print("Failed to decode JSON from the logs, check the log output for errors.", e)
            cluster_resources = None

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
        job_id = f"{job.get_namespace()}-{job.get_name()}"
        
        # Check if the job has already been submitted
        if job_id in self.job_registry:
            return self.job_registry[job_id]
        
        # Prepare runtime environment and job submission parameters
        runtime_env = {
            "working_dir": ".",
            "containers": [{
                "image": job.spec.image,
                "resources": job.spec.resources,
                "replicas": job.spec.replicas,
                "env": job.spec.envs,
                "ports": job.spec.ports
            }]
        }
        # Submit the job to the Ray cluster
        self.client.submit_job(
            entrypoint=job.specluster_resourcesc.run,
            runtime_env=runtime_env,
            submission_id=job_id,
            job_id=job_id,
            entrypoint_num_cpus=job.spec.resources.get(ResourceEnum.CPU.value, 0),
            entrypoint_num_gpus=job.spec.resources.get(ResourceEnum.GPU.value, 0),
            entrypoint_memory=int(job.spec.resources.get(ResourceEnum.MEMORY.value, 0)),
            entrypoint_resources={k: v for k, v in job.spec.resources.items()
                                  if k not in {ResourceEnum.CPU.value,
                                               ResourceEnum.GPU.value,
                                               ResourceEnum.MEMORY.value}
                                               }
        )

        # Store additional information about the job submission
        submission_details = {
            "manager_job_id": job_id,
        }
        self.job_registry[job_id] = job.get_name()

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
        job_id = f"{job.get_namespace()}-{job.get_name()}"
        
        # Check if the job has been submitted
        if job_id not in self.job_registry:
            self.logger.info(f"Job {job_id} not found in job registry.")
            return
        
        ray_job_id = self.job_registry[job_id]
        
        try:
            # Stop the job in the Ray cluster
            self.client.stop_job(ray_job_id)
            self.logger.info(f"Successfully stopped job {ray_job_id} on the Ray cluster.")
            self.client.delete_job(ray_job_id)
            self.logger.info(f"Successfully deleted job {ray_job_id} from the Ray cluster.")
        except Exception as e:
            self.logger.error(f"Failed to stop job {ray_job_id}: {e}")
        
        # Remove the job from the registry
        del self.job_registry[job_id]
        self.logger.info(f"Removed job {job_id} from job registry.")
        

    def get_jobs_status(self) -> Dict[str, Dict[str, Dict[str, str]]]:
        """
        Gets the jobs tasks status. (Map from job name to task mapped to status)
        
        Returns:
            Dict[str, Dict[str, Dict[str, str]]]: A dictionary mapping job names to task statuses.
        """
        self.client = self._connect_to_ray_cluster()
        jobs_dict: Dict[str, Dict[str, Dict[str, str]]] = {
            "tasks": {},
            "containers": {}
        }

        for job_id, job_name in self.job_registry.items():
            print(job_id, job_name)
            try:
                job_status = self.client.get_job_status(job_id)
                self.logger.info(f"Status for job {job_name} (Ray ID: {job_id}): {job_status}")

                if job_name not in jobs_dict["tasks"]:
                    jobs_dict["tasks"][job_name] = {}
                    jobs_dict["containers"][job_name] = {}

                jobs_dict["tasks"][job_name][job_id] = job_status.value
                # Simulate container status & assuming all tasks are in the same container
                jobs_dict["containers"][job_name][job_id] = job_status.value
            except Exception as error:
                self.logger.error(f"Failed to get status for job {job_name} (Ray ID: {job_id}): {error}")
        
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
            job_id = f"{job.get_namespace()}-{job.get_name()}"
            
            # Check if the job has been submitted
            if job_id not in self.job_registry:
                self.logger.info(f"Job {job_id} not found in job registry.")
                return []
            
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
#rm = RayManager("ray", "/home/alex/Documents/skyflow/slurm/slurm", "alex", "34.170.52.164")
#print(rm.cluster_resources)
#print(rm.allocatable_resources)
#mr = RayManager("ray", "/home/alex/Documents/skyflow/slurm/slurm", "alex", "34.132.112.244")
#print(mr.get_cluster_status())

# Create a Job instance
#job = Job()
#job.spec.image = "python:3.8-slim"
#job.spec.resources = {
#    ResourceEnum.CPU.value: 1,
#    ResourceEnum.MEMORY.value: 512  # In MB
#}
#job.spec.run = "echo hello world"
#job.spec.envs = {"ENV_VAR": "value"}
#job.spec.ports = [8080]
#job.spec.replicas = 1
#job.spec.restart_policy = RestartPolicyEnum.NEVER.value
#
## Submit the Job
#rm.submit_job(job)
#time.sleep(5)
#print(rm.get_jobs_status())
#print(rm.get_job_logs(job))