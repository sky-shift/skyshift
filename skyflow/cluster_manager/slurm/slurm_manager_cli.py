# pylint: disable=E1101
"""
Represents the compatability layer over Slurm native CLI.
"""
import logging
import os
import re
import uuid
from typing import Any, Dict, List
import paramiko
from typing import Optional
import yaml

from skyflow import utils
from skyflow.cluster_manager import Manager
from skyflow.cluster_manager.slurm.slurm_compatibility_layer import \
    SlurmCompatiblityLayer
from skyflow.cluster_manager.slurm.slurm_utils import SlurmConfig
from skyflow.templates import (AcceleratorEnum, CRIEnum,
                               Job, ResourceEnum, TaskStatusEnum)
from skyflow.templates.cluster_template import ClusterStatus, ClusterStatusEnum

from skyflow.globals import SLURM_CONFIG_DEFAULT_PATH


# Defines Slurm node states.
SLURM_NODE_AVAILABLE_STATES = {
    'IDLE',
    'ALLOCATED',
    'COMPLETING',
} 

#Defines for job status
SLURM_ACTIVE = {'RUNNING,'
                'COMPLETING'}
SLURM_INIT = {'CONFIGURING', 'PENDING'}
SLURM_FAILED = {'FAILED', 'STOPPED', 'TIMEOUT', 'SUSPENDED', 'PREMPTED'}
SLURM_COMPLETE = {'COMPLETED'}

#Identifying Headers for job submission name
MANAGER_NAME = "skyflow8slurm"


def _send_cli_command(ssh_client: paramiko.SSHClient, command: str):
    """Seconds command locally, or through ssh to a remote cluster
        
        Args: 
            command: bash command to be run.

        Returns:
            stdout
    """
    _, stdout, stderr = ssh_client.exec_command(command)
    return stdout.read().decode().strip(), stderr.read().decode().strip()

def _convert_slurm_output_to_dict(output: str, key_name: str) -> Dict[str, Dict[str, str]]:
    """Converts Slurm list outputs into a dictionary of dictionaries."""
    final_dict = {}
    node_blocks = output.split('\n\n')
    for block in node_blocks:
        node_info = {}
        final_key = None
        lines = block.split('\n')
        for line in lines:
            # Split line by spaces, but keep key-value pairs together
            parts = re.split(r'\s+(?=\S+=)', line.strip())
            for part in parts:
                if '=' in part:
                    key, value = part.split('=', 1)
                    if key == key_name:
                        final_key = value
                    node_info[key] = value
        final_dict[final_key] = node_info
    return final_dict
    
    


class SlurmManagerCLI(Manager):
    """Slurm CLI Compatibility Layer."""
    def __init__(self, 
                 name: str,
                 config_path: str = SLURM_CONFIG_DEFAULT_PATH,
                 logger: Optional[logging.Logger] = None):
        super().__init__(name)
        self.cluster_name = utils.sanitize_cluster_name(name)
        self.config_path = config_path
        if not logger:
            self.logger = logging.getLogger(f"[{name} - K8 Manager]")
        self.config = SlurmConfig(config_path = self.config_path)
        self.auth_config = self.config.get_auth_config(name)
        self.slurm_account = self.auth_config.get('user')  
        # Initalize SSH Client
        self.ssh_client = self.config.get_ssh_client(name)
        
        self.container_manager = self._get_container_manager_type()
        self.runtime_dir = ''
        
        # if self.container_manager.upper() == ContainerEnum.CONTAINERD.value:
        #     self.runtime_dir = _get_config(config_dict, ['tools','runtime_dir'])
        # #Configure Slurm properties
        # #Get slurm user account
        # self.slurm_account = _get_config(config_dict, ['properties', 'account'])
        # #Get slurm time limit
        # self.slurm_time_limit = _get_config(config_dict, ['properties', 'time_limit'])
        #Configure SSH
        #Configure container manager compatibility layer
        # self.compat_layer = SlurmCompatiblityLayer(self.container_manager,
        #     self.runtime_dir, self.slurm_time_limit, self.slurm_account)
        #store resource values
        
        # Maps node name to `sinfo get nodes` outputs.
        # This serves as a cache to fetch information.
        self.slurm_node_dict = {}
        
        self.accelerator_types = None
        # self.get_accelerator_types()
        self.total_resources = None
        self.curr_allocatable = None

    def _get_container_manager_type(self):
        """Finds and reports first available container manager.

            Returns: Container manager on Slurm cluster.
        """
        command = ''
        supported_containers = [e.value for e in CRIEnum]
        for manager_name in supported_containers:
            command = 'if command -v ' + manager_name + ' &> /dev/null;then echo ' + manager_name + ' ;fi'
            stdout, _ = _send_cli_command(self.ssh_client, command)
            if manager_name in stdout:
                return manager_name
        return None

    @property
    def cluster_resources(self) -> Dict[str, Dict[str, float]]:
        """ Gets total available resources of the cluster.
            Returns:
                Dict of each node name and its total resources.
        """
        if not self.slurm_node_dict:
            stdout, _ = _send_cli_command(self.ssh_client, 'scontrol show nodes')
            self.slurm_node_dict = _convert_slurm_output_to_dict(stdout, key_name='NodeName')

        cluster_resources = {}
        for name, node_info in self.slurm_node_dict.items():
            node_state = node_info.get('State', None)
            if node_state not in SLURM_NODE_AVAILABLE_STATES:
                continue
            cpu_total = float(node_info.get('CPUTot', 0))
            mem_total = float(node_info.get('RealMemory', 0))

            cluster_resources[name] = {
                ResourceEnum.CPU.value: cpu_total,
                ResourceEnum.MEMORY.value: mem_total,
            }
            gpu_str = node_info.get('Gres', None)
            if not gpu_str:
                continue
            _, gpu_type, gpu_count = gpu_str.split(':')
            cluster_resources[name][gpu_type] = float(gpu_count)
        cluster_resources = utils.fuzzy_map_gpu(cluster_resources)
        return cluster_resources
    
    @property
    def allocatable_resources(self) -> Dict[str, Dict[str, float]]:
        """ Gets currently allocatable resources.

            Returns:
                Dict of node name and resource property struct.
        """
        if not self.slurm_node_dict:
            stdout, _ = _send_cli_command(self.ssh_client, 'scontrol show nodes')
            self.slurm_node_dict = _convert_slurm_output_to_dict(stdout, key_name='NodeName')

        avail_resources = {}
        has_gres_used = True
        for name, node_info in self.slurm_node_dict.items():
            node_state = node_info.get('State', None)
            if node_state not in SLURM_NODE_AVAILABLE_STATES:
                continue
            cpu_total = float(node_info.get('CPUTot', 0))
            cpu_alloc = float(node_info.get('CPUAlloc', 0))
            mem_total = float(node_info.get('RealMemory', 0))
            mem_alloc = float(node_info.get('AllocMem', 0))

            avail_resources[name] = {
                ResourceEnum.CPU.value: cpu_total - cpu_alloc,
                ResourceEnum.MEMORY.value: mem_total - mem_alloc,
            }
            gpu_str = node_info.get('Gres', None)
            if not gpu_str:
                continue
            _, gpu_type, gpu_count = gpu_str.split(':')
            gpu_alloc_str = node_info.get('GresUsed', None)
            if not gpu_alloc_str:
                has_gres_used = False
                gpu_alloc_count = 0
            else:
                _, _, gpu_alloc_count = gpu_alloc_str.split(':')
            avail_resources[name][gpu_type] = float(gpu_count) - float(gpu_alloc_count)
            print(float(gpu_count) - float(gpu_alloc_count))
        print(avail_resources)
        avail_resources = utils.fuzzy_map_gpu(avail_resources)
        
        # If GresUsed is not found, must calculate GPUs occupied by all running jobs.
        if has_gres_used:
            return avail_resources
        return avail_resources
    

        # #Process gpus
        # command = "scontrol show jobs"
        # #command_output = subprocess.check_output(command, shell=True, text=True)
        # stdout = _send_cli_command(self.ssh_client, command)
        # slurm_jobs_dict = 
        # node_sections = stdout.split('\n\n')
        # for node_info in node_sections:
        #     node_list: List[str] = []
        #     node_list_match = re.search(r' NodeList=(.*?)\n', node_info)
        #     if node_list_match:
        #         values = node_list_match.group(1).split(',')
        #         for item in values:
        #             node_list.append(str(item))
        #     job_state_match = re.search(r'JobState=([^\s]+)', node_info)
        #     job_state = "PENDING"
        #     if job_state_match:
        #         job_state = str(job_state_match.group(1))
        #     if job_state in ('ALLOCATED', 'RUNNING'):
        #         #Get total Gpus utilized by running job
        #         gres_match = re.search(r'Gres=gpu:(\d+)', node_info)
        #         if gres_match:      
        #             gres_used = float(gres_match.group(1))
        #             for node in node_list:
        #                 if available_resources[node][ResourceEnum.GPU.value] - gres_used < 0:
        #                     available_resources[node][ResourceEnum.GPU.value] = 0
        #                 else:
        #                     available_resources[node][ResourceEnum.GPU.value] \
        #                     = available_resources[node][ResourceEnum.GPU.value] - gres_used
        # return self._process_gpu_resources(available_resources)


    def get_cluster_status(self) -> ClusterStatus:
        """ Gets status of the cluster, at least one node must be up.
            Returns:
                Cluster Status struct with total and allocatable resources.
        """
        stdout, stderr = _send_cli_command(self.ssh_client, 'scontrol show partitions')
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
        stdout = _send_cli_command(self.ssh_client, command)
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

    def __del__(self):
        """When deleting SlurmManager, close the SSH connection."""
        self.ssh_client.close()

if __name__ == '__main__':
    api = SlurmManagerCLI(name='my-slurm-cluster')
    status = api.cluster_resources
    print(status)
    print(api.allocatable_resources)
    # print(api.cluster_resources)
    # print("************")
    # print(api.allocatable_resources)
    # containers = api._discover_manager()
    # print(containers)