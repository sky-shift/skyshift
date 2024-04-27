# pylint: disable=E1101
"""
Represents the compatability layer over Slurm native CLI.
"""
import os
import re
import uuid
from typing import Any, Dict, List
import subprocess
import paramiko
import yaml

from skyflow.cluster_manager import Manager
from skyflow.cluster_manager.slurm_compatibility_layer import \
    SlurmCompatiblityLayer
from skyflow.templates import (AcceleratorEnum, ContainerEnum, EndpointObject,
                               Job, ResourceEnum, Service, TaskStatusEnum)
from skyflow.templates.cluster_template import ClusterStatus, ClusterStatusEnum
from skyflow.utils.slurm_utils import (SSHConnectionError, SlurmctldConnectionError, get_config)

from skyflow.globals import SLURM_CONFIG_PATH

SUPPORTED_CONTAINER_SOLUTIONS = [
    "containerd", "singularity", "docker", "podman", "podman-hpc"
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
    def __init__(self, variable_name):
        self.variable_name = variable_name
        super().__init__(f"Variable '{variable_name}' is not provided in the YAML file.")



class SlurmManagerCLI(Manager):
    """ Slurm compatability set for Skyflow."""
    cluster_name = "slurmcluster2"
    def __init__(self):
        """ Constructor which sets up request session, and checks if slurmrestd is reachable.

            Raises:
                Exception: Unable to read config yaml from path SLURMRESTD_CONFIG_PATH.
                ConfigUndefinedError: Value required in config yaml not not defined.
        """
        super().__init__(self.cluster_name)
        self.is_local = False
        config_absolute_path = os.path.expanduser(SLURM_CONFIG_PATH)
        with open(config_absolute_path, 'r') as config_file:
            config_dict = yaml.safe_load(config_file)
            #Configure tools
            config_dict = config_dict[self.cluster_name]

            if str(_get_config(config_dict, ['testing', 'local'], optional=True)) == 'True':
                self.is_local = True
            elif len(str(_get_config(config_dict, ['testing', 'passkey'], optional=True))) > 0:
                self.passkey = str(_get_config(config_dict, ['testing', 'passkey']))
                self.remote_hostname = _get_config(config_dict, ['slurmcli', 'remote_hostname'])
                self.remote_username = _get_config(config_dict, ['slurmcli', 'remote_username'])
                self.ssh_client = paramiko.SSHClient()
                self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                self.check_reachable(True)
            else:
                self.rsa_key_path = _get_config(config_dict, ['slurmcli','rsa_key_path'])
                self.rsa_key_path = os.path.expanduser(self.rsa_key_path)
                if not os.path.exists(self.rsa_key_path):
                    raise ValueError(
                    f'RSA private key file does not exist! {self.rsa_key_path} in \
                    {SLURM_CONFIG_PATH}.')
                self.remote_hostname = _get_config(config_dict, ['slurmcli', 'remote_hostname'])
                self.remote_username = _get_config(config_dict, ['slurmcli', 'remote_username'])
                
                self.rsa_key = paramiko.RSAKey.from_private_key_file(self.rsa_key_path)
                self.ssh_client = paramiko.SSHClient()
                self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                self.check_reachable()
            self.container_manager = self._discover_manager().replace('-', '_')
            self.runtime_dir = ''
            if self.container_manager.upper() == ContainerEnum.CONTAINERD.value:
                self.runtime_dir = _get_config(config_dict, ['tools','runtime_dir'])
            #Configure Slurm properties
            #Get slurm user account
            self.slurm_account = _get_config(config_dict, ['properties', 'account'])
            #Get slurm time limit
            self.slurm_time_limit = _get_config(config_dict, ['properties', 'time_limit'])
        #Configure SSH
        #For testing, allow interfacing with local slurm controller
        
        
        #Configure container manager compatibility layer
        self.compat_layer = SlurmCompatiblityLayer(self.container_manager.lower(),
            self.runtime_dir, self.slurm_time_limit, self.slurm_account)
        #store resource values
        self.accelerator_types = None
        self.get_accelerator_types()
        self.total_resources = None
        self.curr_allocatable = None
    def __del__(self):
        """ Deconstructor
        """
        if not self.is_local:
            self.ssh_client.close()
    def check_reachable(self, uses_passkey = False):
        """ Sanity check to make sure we can SSH into slurm login node.
        """
        try:
        # Connect to the SSH server
            if uses_passkey:
                self.ssh_client.connect(self.remote_hostname,22,self.remote_username,self.passkey)
            else:
                self.ssh_client.connect( hostname = self.remote_hostname,
                    username = self.remote_username, pkey = self.rsa_key )
        except paramiko.AuthenticationException as exception:
            raise SSHConnectionError('Unable to authenticate user, please check configuration')
        except paramiko.SSHException as exception:
            raise SSHConnectionError('SSH protocol negotiation failed, \
            please check if remote server is reachable') from exception
        except Exception as exception:
            raise SSHConnectionError("Unexpected exception") from exception
    def _send_command(self, command):
        """Seconds command locally, or through ssh to a remote cluster
            
            Args: 
                command: bash command to be run.

            Returns:
                stdout
        """
        if self.is_local:
            result = subprocess.run(
                ['bash', '-c', command], 
                capture_output=True, text=True
            )
            if result is None:
                return 'abc'
            return result.stdout.strip()
        else:
            _, stdout, _ = self.ssh_client.exec_command(command)
            return stdout.read().decode().strip()

    def _discover_manager(self):
        """Finds and reports first available container manager.

            Returns: The available container manager name.
        """
        command = ''
        for manager_name in SUPPORTED_CONTAINER_SOLUTIONS:
            command = 'if command -v ' + manager_name + ' &> /dev/null;then echo ' + manager_name + ' ;fi'
        
            stdout = self._send_command(command)
            if manager_name in stdout:
                return manager_name
        return "nocontainer"
    def _process_gpu_resources(
            self, resources: Dict[str,
                                  Dict[str,
                                       float]]) -> Dict[str, Dict[str, float]]:
        """Processes accelerator dict into type and count pairs.

            Args:
                resources: Unprocessed resources of available nodes.
            
            Returns:
                updated resources dict with gpus properly enumerated count assigned.
        """

        if not self.accelerator_types or not set(
                self.accelerator_types).issubset(set(resources.keys())):
            self.accelerator_types = self.get_accelerator_types()

        for node_name, accelerator_type in self.accelerator_types.items():
            gpu_value: float = resources[node_name].pop(ResourceEnum.GPU.value)
            resources[node_name][accelerator_type] = gpu_value
        return resources
    @property
    def cluster_resources(self) -> Dict[str, Dict[str, float]]:
        """ Gets total available resources of the cluster.
            Returns:
                Dict of each node name and its total resources.
        """
        command = "scontrol show nodes"
        #command_output = subprocess.check_output(command, shell=True, text=True)
        stdout = self._send_command(command)
        node_sections = stdout.split('\n\n')

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
            status_match = re.search(r'State=(\w+)\*?', node_info)
            if status_match:
                node_status = status_match.group(1)
                if node_status.upper() in ('DOWN*', 'DOWN'):
                    continue
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
        self.total_resources = self._process_gpu_resources(cluster_resources)
        #Update cluster properties, since this only needs to be called once
        return self.total_resources
    @property
    def allocatable_resources(self) -> Dict[str, Dict[str, float]]:
        """ Gets currently allocatable resources.

            Returns:
                Dict of node name and resource property struct.
        """
        command = "scontrol show nodes"
        #command_output = subprocess.check_output(command, shell=True, text=True)
        stdout = self._send_command(command)
        node_sections = stdout.split('\n\n')
        available_resources = {}
        for node_info in node_sections:
            cpu_total = 0.0
            mem_total = 0.0
            gres_count = 0.0
            node_name = ''
            status_match = re.search(r'State=(\w+)\*?', node_info)
            if status_match:
                node_status = status_match.group(1)
                if node_status.upper() in ('DOWN*', 'DOWN'):
                    continue
            #Get total CPUs in node
            node_name_match = re.search(r'NodeName=(\w+)\s', node_info)
            if node_name_match:
                node_name = node_name_match.group(1)
            cpu_total_match = re.search(r'CPUAlloc=(\d+)', node_info)
            if cpu_total_match:
                cpu_total = float(self.total_resources[node_name][ResourceEnum.CPU.value]) - float(cpu_total_match.group(1))
            #Get total memory in node
            mem_total_match = re.search(r'FreeMem=(\d+)', node_info)
            if mem_total_match:
                mem_total = float(mem_total_match.group(1))
            accelerator_type = AcceleratorEnum.UNKGPU
            has_gpus = False
            for key in self.total_resources[node_name]:
                if type(key) == AcceleratorEnum:
                    accelerator_type = key
                    has_gpus = True
            if has_gpus:
                available_resources[node_name] = {
                    ResourceEnum.CPU.value: float(cpu_total),
                    ResourceEnum.MEMORY.value: float(mem_total),
                    ResourceEnum.GPU.value: self.total_resources[node_name][accelerator_type]
                }
            else:
                available_resources[node_name] = {
                ResourceEnum.CPU.value: float(cpu_total),
                ResourceEnum.MEMORY.value: float(mem_total),
                ResourceEnum.GPU.value: 0.0
            }

        #Process gpus
        command = "scontrol show jobs"
        #command_output = subprocess.check_output(command, shell=True, text=True)
        stdout = self._send_command(command)
        node_sections = stdout.split('\n\n')
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
        return self._process_gpu_resources(available_resources)
    def get_accelerator_types(self) -> Dict[str, AcceleratorEnum]:
        """ Gets accelerator type available on each node.
            Returns:
                Dict of node name and respective accelerator type.
        """
        if self.accelerator_types is not None:
            return self.accelerator_types
        command = "scontrol show nodes"
        #command_output = subprocess.check_output(command, shell=True, text=True)
        stdout = self._send_command(command)
        node_sections = stdout.split('\n\n')
        
        node_gpus = {}
        for node_info in node_sections:
            status_match = re.search(r'State=(\w+)\*?', node_info)
            if status_match:
                node_status = status_match.group(1)
                if node_status.upper() in ('DOWN*', 'DOWN'):
                    continue
            node_name = ''
            gpu_enum = AcceleratorEnum.UNKGPU
            node_name_match = re.search(r'NodeName=(\w+)\s', node_info)
            if node_name_match:
                node_name = node_name_match.group(1)
            gpu_model_match = re.search(r'Gres=gpu:([^:]+)', node_info)
            if gpu_model_match:
                gpu_model = str(gpu_model_match.group(1)).lower()
                for member in AcceleratorEnum:
                    if member.value.lower() in gpu_model:
                        gpu_enum = member
                node_gpus[node_name] = gpu_enum
        self.accelerator_types = node_gpus
        return node_gpus
    def get_cluster_status(self) -> ClusterStatus:
        """ Gets status of the cluster, at least one node must be up.
            Returns:
                Cluster Status struct with total and allocatable resources.
        """
        command = 'scontrol show partitions'

        stdout = self._send_command(command)
        cluster_info = stdout

        if 'State=UP' in cluster_info:
            return ClusterStatus(
                status=ClusterStatusEnum.READY.value,
                capacity=self.cluster_resources,
                allocatable_capacity=self.allocatable_resources,
        )
        return ClusterStatus(
                status=ClusterStatusEnum.ERROR.value,
                capacity=self.cluster_resources,
                allocatable_capacity=self.allocatable_resources,
        )
    def get_jobs_status(self) -> Dict[str, Dict[str, TaskStatusEnum]]:
        """ Gets status' of all managed jobs running under skyflow slurm user account.

            Returns:
                Dict of jobs with their status as the value.

        """
        command = 'squeue ' + '-u ' + self.slurm_account + ' -o "%.18i %.30j %.2t"'
        #command_output = subprocess.check_output(command, shell=True, text=True)
        stdout = self._send_command(command)
        jobs_info = stdout.split('\n')
        #jobs_info = subprocess.check_output(command, shell=True, text=True)
        jobs_info = jobs_info[1:]
        #Create dict of only managed jobs. [Job ID, Job Name, Status]
        jobs_dict: Dict[str, Dict[str, TaskStatusEnum]] = {"tasks": {}, "containers": {}}
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
                        jobs_dict["tasks"][slurm_job_name] = TaskStatusEnum.RUNNING
                    elif status == 'PD':
                        jobs_dict["tasks"][slurm_job_name] = TaskStatusEnum.PENDING
                    elif status == 'I':
                        jobs_dict["tasks"][slurm_job_name] = TaskStatusEnum.INIT
                    elif status == 'F':
                        jobs_dict["tasks"][slurm_job_name] = TaskStatusEnum.FAILED
        return jobs_dict
    def _get_matching_job_names(self, match_name: str):
        """ Gets a list of jobs with matching names.

            Arg:
                match_name: Name of job to match against.

            Returns:
                List of all job names that match match_name.

        """
        command = 'squeue -u ' + self.slurm_account + ' --format="%j"'
        stdout = self._send_command(command)
        all_job_names = stdout.split('\n')
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

        stdout = self._send_command(command)
        sbatch_output = stdout

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
        stdout = self._send_command(command)
        del_response = stdout

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
def _get_config(config_dict, key, optional=False) -> str:
    """Fetches key from config dict extracted from yaml.
        Allows optional keys to be fetched without returning an error.

        Args: 
            config_dict: dictionary of nested key value pairs.
            key: array of keys, forming the nested key path.
            optional: whether the key in the yaml is optional or not.
        Returns:
            key: the value associated with the key path
    """
        
    config_val = config_dict
    nested_path = ''
    if not optional:
        for i in range(len(key)):
            nested_path += key[i]
            if key[i] not in config_val:
                raise ConfigUndefinedError(nested_path)
            else:
                config_val = config_val[key[i]]
    else:
        for i in range(len(key)):
            nested_path += key[i]
            if key[i] not in config_val:
                return ''
            else:
                config_val = config_val[key[i]]
    return config_val
if __name__ == '__main__':
    api = SlurmManagerCLI()
    #status = api.get_cluster_status()
    #print(status.status)
    #print(api.cluster_resources)
    #print("************")
    #print(api.allocatable_resources)
    #containers = api._discover_manager()
    #print(containers)