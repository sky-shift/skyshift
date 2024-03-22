# pylint: disable=E1101
"""
Represents the compatability layer over Slurm native CLI.
"""
import os
import re
import uuid
from typing import Any, Dict, List

import paramiko
import yaml

from skyflow.cluster_manager import Manager
from skyflow.cluster_manager.slurm_compatibility_layer import \
    SlurmCompatiblityLayer
from skyflow.templates import (AcceleratorEnum, ContainerEnum, EndpointObject,
                               Job, ResourceEnum, Service, TaskStatusEnum)
from skyflow.templates.cluster_template import ClusterStatus, ClusterStatusEnum

SLURM_CONFIG_PATH = '~/.skyconf/slurmconf.yaml'
SUPPORTED_CONTAINER_SOLUTIONS = [
    "containerd", "singularity", "docker", "podman", "podmanhpc"
]

#Defines for job status
SLURM_ACTIVE = {'RUNNING,'
                'COMPLETING'}
SLURM_INIT = {'CONFIGURING', 'PENDING'}
SLURM_FAILED = {'FAILED', 'STOPPED', 'TIMEOUT', 'SUSPENDED', 'PREMPTED'}
SLURM_COMPLETE = {'COMPLETED'}
#Identifying Headers for job submission name
MANAGER_NAME = "skyflow8slurm"
#Slurm head node number

HEAD_NODE = 0


class ConfigUndefinedError(Exception):
    """ Raised when there is an error in slurm config yaml. """

class SlurmctldConnectionError(Exception):
    """ Raised when there is an error connecting to slurmctld. """
class SSHConnectionError(Exception):
    """ Raised when there is an error establishing SSH connection to slurm cluster. """
class SlurmManagerCLI(Manager):
    """ Slurm compatability set for Skyflow."""

    def __init__(self):
        """ Constructor which sets up request session, and checks if slurmrestd is reachable.

            Raises:
                Exception: Unable to read config yaml from path SLURMRESTD_CONFIG_PATH.
                ConfigUndefinedError: Value required in config yaml not not defined.
        """
        super().__init__("slurm")
        config_absolute_path = os.path.expanduser(SLURM_CONFIG_PATH)
        with open(config_absolute_path, 'r') as config_file:
            try:
                config_dict = yaml.safe_load(config_file)
            except ValueError as exception:
                raise Exception(
                    f'Unable to load {SLURM_CONFIG_PATH}, check if file exists.'
                ) from exception
            #Configure tools
            try:
                self.container_manager = config_dict['tools']['container']
            except ConfigUndefinedError as exception:
                raise ConfigUndefinedError(
                    f'Missing container manager {self.container_manager} in \
                    {SLURM_CONFIG_PATH}.') from exception
            if self.container_manager.lower() not in SUPPORTED_CONTAINER_SOLUTIONS:
                raise ValueError(
                    f'Unsupported container manager {self.container_manager} in \
                        {SLURM_CONFIG_PATH}.') from exception
            self.runtime_dir = ''
            if self.container_manager.upper() == ContainerEnum.CONTAINERD.value:
                try:
                    self.runtime_dir = config_dict['tools']['runtime_dir']
                except ConfigUndefinedError as exception:
                    raise ConfigUndefinedError(
                        f'Missing runtime_dir for {self.container_manager} in \
                            {SLURM_CONFIG_PATH}.') from exception
            if self.container_manager.lower() not in SUPPORTED_CONTAINER_SOLUTIONS:
                raise ValueError(
                    f'Unsupported container manager {self.container_manager} in \
                        {SLURM_CONFIG_PATH}.') from exception
            #Configure SSH
            try:
                #Get RSA key path
                self.rsa_key_path = config_dict['slurmcli']['rsa_key_path']
                self.rsa_key_path = os.path.expanduser(self.rsa_key_path)
                if not os.path.exists(self.rsa_key_path):
                    raise ConfigUndefinedError(
                    f'RSA private key file does not exist!{self.rsa_key_path} in \
                    {SLURM_CONFIG_PATH}.')
            except ConfigUndefinedError as exception:
                raise ConfigUndefinedError(
                    f'Missing RSA private key path {self.rsa_key_path} in \
                    {SLURM_CONFIG_PATH}.') from exception
            try:
                #Get remote hostname
                self.remote_hostname = config_dict['slurmcli']['remote_hostname']
            except ConfigUndefinedError as exception:
                raise ConfigUndefinedError(
                    f'Missing hostname of the slurm cluster to SSH into{self.remote_hostname} in \
                    {SLURM_CONFIG_PATH}.') from exception
            try:
                #Get remote username
                self.remote_username = config_dict['slurmcli']['remote_username']
            except ConfigUndefinedError as exception:
                raise ConfigUndefinedError(
                    f'Missing username of the slurm cluster to SSH into{self.remote_hostname} in \
                    {SLURM_CONFIG_PATH}.') from exception
            #Configure Slurm properties
            try:
                #Get slurm user account
                self.slurm_account = config_dict['properties']['account']
            except ConfigUndefinedError as exception:
                raise ConfigUndefinedError(
                    f'Missing slurm_account username needed \
                    for job submission{self.slurm_account} in \
                    {SLURM_CONFIG_PATH}.') from exception
            try:
                #Get slurm time limit
                self.slurm_time_limit = config_dict['properties']['time_limit']
            except ConfigUndefinedError as exception:
                raise ConfigUndefinedError(
                    f'Slurm time limit{self.slurm_account} in \
                    {SLURM_CONFIG_PATH}.') from exception
        #Configure SSH
        self.rsa_key = paramiko.RSAKey.from_private_key_file(self.rsa_key_path)
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.check_reachable()
        #Configure container manager compatibility layer
        self.compat_layer = SlurmCompatiblityLayer(self.container_manager.lower(),
            self.runtime_dir, self.slurm_time_limit, self.slurm_account)

        #store resource values
        self.accelerator_types = None
        self.get_accelerator_types()
    def __del__(self):
        """ Deconstructor
        """
        self.ssh_client.close()
    def check_reachable(self):
        """ Sanity check to make sure we can SSH into slurm login node.
        """
        try:
        # Connect to the SSH server
            self.ssh_client.connect( hostname = self.remote_hostname,
                username = self.remote_username, pkey = self.rsa_key )
        except paramiko.AuthenticationException as exception:
            raise SSHConnectionError('Unable to authenticate user, please check configuration')
        except paramiko.SSHException as exception:
            raise SSHConnectionError('SSH protocol negotiation failed, \
            please check if remote server is reachable') from exception
        except Exception as exception:
            raise SSHConnectionError("Unexpected exception") from exception
    @property
    def cluster_resources(self) -> Dict[str, Dict[str, float]]:
        """ Gets total available resources of the cluster.
            Returns:
                Dict of each node name and its total resources.
        """
        command = "scontrol show nodes"
        #command_output = subprocess.check_output(command, shell=True, text=True)
        _, stdout, _ = self.ssh_client.exec_command(command)
        node_sections = stdout.read().decode().strip().split('\n\n')

        cluster_resources = {}
        for node_info in node_sections:
            cpu_total = 0.0
            mem_total = 0.0
            gres_count = 0.0
            node_name = ''
            #Get total CPUs in node
            node_name_match = re.search(r'NodeName=(\w+)\s', node_info)
            if node_name_match:
                node_name = node_name_match.group(1)
            cpu_total_match = re.search(r'CPUTot=(\d+)', node_info)
            if cpu_total_match:
                cpu_total = float(cpu_total_match.group(1))
            #Get total memory in node
            mem_total_match = re.search(r'RealMemory=(\d+)', node_info)
            if mem_total_match:
                mem_total = float(mem_total_match.group(1))
            #Get total GPUs in node
            gres_match = re.search(r'Gres=gpu:\w+:(\d+)', node_info)
            if gres_match:
                gres_count = float(gres_match.group(1))
            cluster_resources[node_name] = {
                ResourceEnum.CPU.value: float(cpu_total),
                ResourceEnum.MEMORY.value: float(mem_total),
                ResourceEnum.GPU.value: float(gres_count)
            }
        #Update cluster properties, since this only needs to be called once
        self.total_resources = cluster_resources
        return cluster_resources
    @property
    def allocatable_resources(self) -> Dict[str, Dict[str, float]]:
        """ Gets currently allocatable resources.

            Returns:
                Dict of node name and resource property struct.
        """
        command = "scontrol show nodes"
        #command_output = subprocess.check_output(command, shell=True, text=True)
        _, stdout, _ = self.ssh_client.exec_command(command)
        node_sections = stdout.read().decode().strip().split('\n\n')
        available_resources = {}
        for node_info in node_sections:
            cpu_total = 0.0
            mem_total = 0.0
            gres_count = 0.0
            node_name = ''
            #Get total CPUs in node
            node_name_match = re.search(r'NodeName=(\w+)\s', node_info)
            if node_name_match:
                node_name = node_name_match.group(1)
            cpu_total_match = re.search(r'CPUAlloc=(\d+)', node_info)
            if cpu_total_match:
                cpu_total = float(cpu_total_match.group(1))
            #Get total memory in node
            mem_total_match = re.search(r'AllocMem=(\d+)', node_info)
            if mem_total_match:
                mem_total = float(mem_total_match.group(1))
            available_resources[node_name] = {
                ResourceEnum.CPU.value: float(cpu_total),
                ResourceEnum.MEMORY.value: float(mem_total),
                ResourceEnum.GPU.value: self.total_resources[node_name][ResourceEnum.GPU.value]
            }

        #Process gpus
        command = "scontrol show jobs"
        #command_output = subprocess.check_output(command, shell=True, text=True)
        _, stdout, _ = self.ssh_client.exec_command(command)
        node_sections = stdout.read().decode().strip().split('\n\n')
        for node_info in node_sections:
            node_list: List[str] = []
            node_list_match = re.search(r' NodeList=(.*?)\n', node_info)
            if node_list_match:
                values = node_list_match.group(1).split(',')
                for item in values:
                    node_list.append(str(item))
            job_state_match = re.search(r'JobState=([^\s]+)', node_info)
            job_state = "PENDING"
            if job_state_match:
                job_state = str(job_state_match.group(1))
            if job_state in ('ALLOCATED', 'RUNNING'):
                #Get total Gpus utilized by running job
                gres_match = re.search(r'Gres=gpu:(\d+)', node_info)
                if gres_match:      
                    gres_used = float(gres_match.group(1))
                    for node in node_list:
                        if available_resources[node][ResourceEnum.GPU.value] - gres_used < 0:
                            available_resources[node][ResourceEnum.GPU.value] = 0
                        else:
                            available_resources[node][ResourceEnum.GPU.value] \
                            = available_resources[node][ResourceEnum.GPU.value] - gres_used

        self.curr_allocatable = available_resources
        return available_resources
    def get_accelerator_types(self) -> Dict[str, AcceleratorEnum]:
        """ Gets accelerator type available on each node.
            Returns:
                Dict of node name and respective accelerator type.
        """
        if self.accelerator_types is not None:
            return self.accelerator_types
        command = "scontrol show nodes"
        #command_output = subprocess.check_output(command, shell=True, text=True)
        _, stdout, _ = self.ssh_client.exec_command(command)
        node_sections = stdout.read().decode().strip().split('\n\n')
        
        node_gpus = {}
        for node_info in node_sections:
            node_name = ''
            node_name_match = re.search(r'NodeName=(\w+)\s', node_info)
            if node_name_match:
                node_name = node_name_match.group(1)
            gpu_model_match = re.search(r'Gres=gpu:([^:]+)', node_info)
            if gpu_model_match:
                gpu_model = str(gpu_model_match.group(1)).lower()
                #TODO, GPU ENUMS
                if 'v100' in gpu_model:
                    gpu_enum = AcceleratorEnum.V100
                elif 'a100' in gpu_model:
                    gpu_enum = AcceleratorEnum.A100
                else:
                    gpu_enum = AcceleratorEnum.UNKGPU
                node_gpus[node_name] = gpu_enum
        self.accelerator_types = node_gpus
        return node_gpus
    def get_cluster_status(self):
        """ Gets status of the cluster, at least one node must be up.
            Returns:
                Cluster Status struct with total and allocatable resources.
        """
        command = 'scontrol show partitions'

        _, stdout, _ = self.ssh_client.exec_command(command)
        cluster_info = stdout.read().decode().strip()

        if 'State=UP' in cluster_info:
            return ClusterStatus(
                status=ClusterStatusEnum.READY.value,
                capacity=self.total_resources,
                allocatable_capacity=self.allocatable_resources,
        )
        return ClusterStatus(
                status=ClusterStatusEnum.ERROR.value,
                capacity=self.total_resources,
                allocatable_capacity=self.allocatable_resources,
        )
    def get_jobs_status(self) -> Dict[str, TaskStatusEnum]:
        """ Gets status' of all managed jobs running under skyflow slurm user account.

            Returns:
                Dict of jobs with their status as the value.

        """
        command = 'squeue ' + '-u ' + self.slurm_account + ' -o "%.18i %.30j %.2t"'
        #command_output = subprocess.check_output(command, shell=True, text=True)
        _, stdout, _ = self.ssh_client.exec_command(command)
        jobs_info = stdout.read().decode().strip().split('\n')
        #jobs_info = subprocess.check_output(command, shell=True, text=True)
        jobs_info = jobs_info.split('\n')
        jobs_info = jobs_info[1:]
        #Create dict of only managed jobs. [Job ID, Job Name, Status]
        jobs_dict: Dict[str, TaskStatusEnum] = {}
        for job in jobs_info:
            job_property = job.split()
            #check if this is a managed job
            job_name = job_property[1]
            if MANAGER_NAME in job_name:
                status = job_property[2]
                #Remove UUID, and manager header
                split_str_ids = job_name.split('-')[:3]
                if split_str_ids[
                    0] == MANAGER_NAME:  #Job is Managed by skyflow
                    slurm_job_name = f'{split_str_ids[1]}-{split_str_ids[2]}'
                    if status == 'R':
                        jobs_dict[slurm_job_name] = TaskStatusEnum.RUNNING
                    elif status == 'PD':
                        jobs_dict[slurm_job_name] = TaskStatusEnum.PENDING
                    elif status == 'I':
                        jobs_dict[slurm_job_name] = TaskStatusEnum.INIT
                    elif status == 'F':
                        jobs_dict[slurm_job_name] = TaskStatusEnum.FAILED
        return jobs_dict
    def _get_matching_job_names(self, match_name: str):
        """ Gets a list of jobs with matching names.

            Arg:
                match_name: Name of job to match against.

            Returns:
                List of all job names that match match_name.

        """
        command = 'squeue -u ' + self.slurm_account + ' --format="%j"'
        _, stdout, _ = self.ssh_client.exec_command(command)
        all_job_names = stdout.read().decode().strip().split('\n')
        #all_job_names = subprocess.check_output(command, shell=True, text=True).split('\n')
        all_job_names = all_job_names[1:]
        matching_job_names = []
        for name in all_job_names:
            split_str_ids = name.split('-')[:3]
            if len(split_str_ids) > 1:
                slurm_job_name = f'{split_str_ids[1]}-{split_str_ids[2]}'
                if slurm_job_name == match_name:
                    matching_job_names.append(slurm_job_name)
        return matching_job_names
    def submit_job(self, job: Job) -> Dict[str, Any]:
        """
        Submit a job to the cluster, represented as a group of pods.
        This method is supposed to be idempotent.
        If the job has already been submitted, it does nothing.

        Args:
            job: Job object containing job properties

        Returns:
            The submitted job name, job ID, and any job submission api responses.
        """
        api_responses = []
        job_name = job.metadata.name
        # Check if the job has already been submitted.
        matching_jobs = self._get_matching_job_names(job_name)
        if job_name in matching_jobs:
            # Job has already been submitted.
            first_object = matching_jobs[0]
            api_responses.append("Deny resubmission of identical job")
            return {
                'manager_job_id': first_object,
                'slurm_job_id': 0,
                'api_responses': api_responses,
            }

        slurm_job_name = f"{MANAGER_NAME}-{job_name}-{uuid.uuid4().hex[:8]}"

        command = self.compat_layer.create_slurm_sbatch(job) + ' -J ' + slurm_job_name

        _, stdout, _ = self.ssh_client.exec_command(command)
        sbatch_output = stdout.read().decode().strip()

        api_responses.append(sbatch_output)
        job_id_match = re.search(r'\b\d+(?:_\d+)*\b', sbatch_output)
        slurm_job_id = '0'
        if job_id_match:
            slurm_job_id = str(job_id_match.group(0))
        else:
            api_responses.append("Failed to require job ID")
        #Assign slurm specific job id for future deletion search
        job.status.job_ids['slurm_job_id'] = slurm_job_id
        return {
            'manager_job_id': slurm_job_name,
            'slurm_job_id': slurm_job_id,
            'api_responses': api_responses,
        }
    def delete_job(self, job: Job) -> list[str]:
        """ Deletes a job from the slurm controller.

            Args:
                job: Job object to be deleted.
            Returns:
                Any api responses
        """
        api_responses = []
        if 'slurm_job_id' not in job.status.job_ids:
            api_responses.append(
                'No slurm job ID parameter, refusing to delete')
            return api_responses
        command = 'scancel ' + str(job.status.job_ids['slurm_job_id'])
        _, stdout, _ = self.ssh_client.exec_command(command)
        del_response = stdout.read().decode().strip()

        if del_response == '':
            api_responses.append("Successfully cancelled")
        api_responses.append(del_response)
        return api_responses
    def get_service_status(self) -> Dict[str, Dict[str, str]]:
        """ Fetches current status of service deployed.

            Returns: Dict of all service names and their properties.

        """
        raise NotImplementedError
    @staticmethod
    def convert_yaml(job: Job):
        """Converts generic yaml file into manager specific format"""
        raise NotImplementedError
    def create_or_update_service(self, service: Service):
        """Creates a service, or updates properites of existing service."""
        raise NotImplementedError

    def get_pods_with_selector(self, label_selector: Dict[str, str]):
        """Gets all pods matching a label."""
        raise NotImplementedError
    def delete_service(self, service: Service):
        """Deletes a service."""
        raise NotImplementedError
    def create_endpoint_slice(  # pylint: disable=too-many-locals, too-many-branches
        self, name: str, cluster_name, endpoint: EndpointObject):
        """Creates/updates an endpint slice."""
        raise NotImplementedError
if __name__ == '__main__':
    api = SlurmManagerCLI()