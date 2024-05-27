"""
Represents the compatability layer over Slurm native CLI.
"""
import logging
import math
import os
import re
import tempfile
import uuid
from typing import Any, Dict, List, Optional

from fastapi import WebSocket
from jinja2 import Environment, FileSystemLoader, select_autoescape

from skyflow import utils
from skyflow.cluster_manager.manager import Manager
from skyflow.cluster_manager.slurm import slurm_utils
from skyflow.cluster_manager.slurm.slurm_compatibility_layer import \
    SlurmCompatiblityLayer
from skyflow.globals import SLURM_CONFIG_DEFAULT_PATH
from skyflow.templates import CRIEnum, Job, ResourceEnum, TaskStatusEnum
from skyflow.templates.cluster_template import ClusterStatus, ClusterStatusEnum

logging.getLogger("paramiko").setLevel(logging.WARNING)

#Defines for job status
SLURM_JOB_ACTIVE = {'RUNNING', 'COMPLETING'}
SLURM_JOB_INIT = {'CONFIGURING', 'PENDING'}
SLURM_JOB_FAILED = {
    'CANCELLED', 'FAILED', 'STOPPED', 'TIMEOUT', 'SUSPENDED', 'PREMPTED'
}
SLURM_JOB_COMPLETE = {'COMPLETED'}

# Prefix for all jobs managed by Skyflow.
JOB_PREPEND_STR = "skyflow2slurm"
# Remote directory for storing scripts on Slurm node.
REMOTE_SCRIPT_DIR = "~/.skyconf"
# Defines Slurm node states.
SLURM_NODE_AVAILABLE_STATES = {
    'IDLE',
    'IDLE+CLOUD',
    'ALLOCATED',
    'ALLOCATED+CLOUD',
    'COMPLETING',
}


class SlurmConnectionError(Exception):
    """Raised when there is an error connecting to the Slurm control plane."""


def _override_resources(job: Job) -> Job:
    """
        Overrides resources to fit minimum allocatable resources for Slurm.
        Arg:
            job: The job to be scheduled.
        Returns:
            Job with the corrected resources.
    """
    resources = job.spec.resources
    res_cpus = float(resources[ResourceEnum.CPU.value])
    res_memory = float(resources[ResourceEnum.MEMORY.value])
    # CPUs cannot be fractional.
    resources[ResourceEnum.CPU.value] = math.ceil(res_cpus)
    # A job must occupy at least 32 MB of memory.
    resources[ResourceEnum.MEMORY.value] = max(32, res_memory)
    job.spec.resources = resources
    return job


# pylint: disable=too-many-locals,too-many-branches
def convert_slurm_job_table_to_status(
        output: str) -> Dict[str, Dict[str, str]]:
    """Converts a job table into a dictionary of job statuses."""
    lines = output.strip().split('\n')
    headers = lines[0].split()
    job_dict: Dict[str, Dict[str, str]] = {}
    # Get the starting positions of each header
    header_positions = [m.start() for m in re.finditer(r'\S+', lines[0])]
    true_job_name = None
    for line in lines[2:]:
        job_info = {}
        for i, header in enumerate(headers):
            start_pos = header_positions[i]
            end_pos = header_positions[
                i + 1] if i + 1 < len(header_positions) else None
            job_info[header] = line[start_pos:end_pos].strip()
        job_name = job_info['JobName']
        job_id_str = job_info['JobID']
        if '.' not in job_id_str:
            if JOB_PREPEND_STR not in job_name:
                skip = True
                continue
            skip = False
            # Remove JOB_PREPREND_STR from job name
            true_job_name = job_name[len(JOB_PREPEND_STR) + 1:]
            true_job_name = '-'.join(true_job_name.split('-')[:-1])
            if true_job_name is None:
                skip = True
            else:
                job_dict[true_job_name] = {}
            continue
        if skip:
            continue
        _, task_index = job_id_str.split('.')
        if not task_index or not true_job_name:
            continue
        try:
            int(task_index)
        except ValueError:
            continue
        job_state = job_info['State']
        if job_state in SLURM_JOB_ACTIVE:
            job_dict[true_job_name][task_index] = TaskStatusEnum.RUNNING.value
        elif job_state in SLURM_JOB_INIT:
            job_dict[true_job_name][task_index] = TaskStatusEnum.INIT.value
        elif job_state in SLURM_JOB_FAILED:
            job_dict[true_job_name][task_index] = TaskStatusEnum.FAILED.value
        elif job_state in SLURM_JOB_COMPLETE:
            job_dict[true_job_name][
                task_index] = TaskStatusEnum.COMPLETED.value
        else:
            continue
    final_jobs_dict = {k: v for k, v in job_dict.items() if v}
    return final_jobs_dict


class SlurmManagerCLI(Manager):  # pylint: disable=too-many-instance-attributes
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
        self.config = slurm_utils.SlurmConfig(config_path=self.config_path)
        self.auth_config = self.config.get_auth_config(name)
        self.user = self.auth_config.get('user', '')
        # Initalize SSH Client
        self.ssh_client = self.config.get_ssh_client(name)
        # Create directory for jobs and logs.
        stdout, stderr = slurm_utils.send_cli_command(
            self.ssh_client, f'mkdir -p {REMOTE_SCRIPT_DIR}; echo $HOME')
        if stderr:
            raise SlurmConnectionError(
                'Failed to execute command on remote Slurm node.')
        self.remote_sky_dir = REMOTE_SCRIPT_DIR.replace('~', stdout)

        self.container_manager = self._get_container_manager_type()
        # Initialize CRI compatibility layer
        self.compat_layer = SlurmCompatiblityLayer(self.container_manager,
                                                   user=self.user)
        # Maps node name to `sinfo get nodes` outputs.
        # This serves as a cache to fetch information.
        self.slurm_node_dict: Dict[str, Any] = {}
        # Job name and IDs (Jobs that still need to be kept track by Skyflow)
        # that should be tracked by the manager.
        self.job_cache: Dict[str, str] = {}

    def _get_container_manager_type(self):
        """Finds and reports first available container manager.

            Returns: Container manager on Slurm cluster.
        """
        command = ''
        supported_containers = [e.value for e in CRIEnum]
        for manager_name in supported_containers:
            command = 'if command -v ' + manager_name + \
                ' &> /dev/null;then echo ' + manager_name + ' ;fi'
            stdout, _ = slurm_utils.send_cli_command(self.ssh_client, command)
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
            stdout, _ = slurm_utils.send_cli_command(self.ssh_client,
                                                     'scontrol show nodes')
            self.slurm_node_dict = slurm_utils.convert_slurm_block_to_dict(
                stdout, key_name='NodeName')
        cluster_resources = {}
        for name, node_info in self.slurm_node_dict.items():
            node_state = node_info.get('State', None)
            node_available = any(node_state in j
                                 for j in SLURM_NODE_AVAILABLE_STATES)
            if not node_available:
                continue
            cpu_total = float(node_info.get('CPUTot', 0))
            mem_total = float(node_info.get('RealMemory', 0))

            cluster_resources[name] = {
                ResourceEnum.CPU.value: cpu_total,
                ResourceEnum.MEMORY.value: mem_total,
            }
            gpu_str = node_info.get('Gres', None)
            if not gpu_str or 'null' in gpu_str:
                continue
            _, gpu_type, gpu_count = gpu_str.split(':')
            cluster_resources[name][gpu_type] = float(gpu_count)
        cluster_resources = utils.fuzzy_map_gpu(cluster_resources)
        return cluster_resources

    @property
    def allocatable_resources(self) -> Dict[str, Dict[str, float]]:  # pylint: disable=too-many-locals
        """ Gets currently allocatable resources.

            Returns:
                Dict of node name and resource property struct.
        """
        if not self.slurm_node_dict:
            stdout, _ = slurm_utils.send_cli_command(self.ssh_client,
                                                     'scontrol show nodes')
            self.slurm_node_dict = slurm_utils.convert_slurm_block_to_dict(
                stdout, key_name='NodeName')

        avail_resources = {}
        for name, node_info in self.slurm_node_dict.items():
            node_state = node_info.get('State', None)
            node_available = any(node_state in j
                                 for j in SLURM_NODE_AVAILABLE_STATES)
            if not node_available:
                continue
            # Fetch resources from dict.
            cpu_total = float(node_info.get('CPUTot', 0))
            cpu_alloc = float(node_info.get('CPUAlloc', 0))
            mem_total = float(node_info.get('RealMemory', 0))
            mem_alloc = float(node_info.get('AllocMem', 0))

            avail_resources[name] = {
                ResourceEnum.CPU.value: cpu_total - cpu_alloc,
                ResourceEnum.MEMORY.value: mem_total - mem_alloc,
            }
            # Special case handling for accelerators.
            gpu_str = node_info.get('Gres', None)
            if not gpu_str or 'null' in gpu_str:
                continue
            _, gpu_type, gpu_count = gpu_str.split(':')
            gpu_alloc_str = node_info.get('GresUsed', None)
            if not gpu_alloc_str or 'null' in gpu_alloc_str:
                gpu_alloc_count = 0
            else:
                _, _, gpu_alloc_count = gpu_alloc_str.split(':')
            avail_resources[name][gpu_type] = float(gpu_count) - float(
                gpu_alloc_count)
        avail_resources = utils.fuzzy_map_gpu(avail_resources)
        return avail_resources

    def get_cluster_status(self) -> ClusterStatus:
        """ Gets status of the cluster, at least one node must be up.
            Returns:
                Cluster Status struct with total and allocatable resources.
        """
        self.slurm_node_dict = {}
        _, stderr = slurm_utils.send_cli_command(self.ssh_client,
                                                 'scontrol show partitions')
        if not stderr:
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

    def get_jobs_status(self) -> Dict[str, Dict[str, Dict[str, str]]]:
        """ Gets status' of all managed jobs running under skyflow slurm user account.

            Returns:
                Dict of jobs with their status as the value.

        """
        all_jobs_command = (
            f'sacct -u {self.user} --format=JobID%-30,'
            'JobName%-100,State%-30,NodeList%-50,AllocTRES%-100 '
            '--starttime=now-5days')
        jobs_dict: Dict[str, Dict[str, Dict[str, str]]] = {
            "tasks": {},
            "containers": {}
        }
        #command_output = subprocess.check_output(command, shell=True, text=True)
        stdout, _ = slurm_utils.send_cli_command(self.ssh_client,
                                                 all_jobs_command)
        jobs_info = convert_slurm_job_table_to_status(stdout)

        jobs_dict['tasks'] = jobs_info
        return jobs_dict

    def _get_matching_job_names(self, match_name: str):
        """ Gets a list of jobs with matching names.

            Arg:
                match_name: Name of job to match against.
`
            Returns:
                List of all job names that match match_name.
        """
        command = 'squeue -u ' + self.user + ' --format="%j"'
        stdout, _ = slurm_utils.send_cli_command(self.ssh_client, command)
        all_job_names = stdout.split('\n')
        all_job_names = all_job_names[1:]
        matching_job_names = []
        for name in all_job_names:
            split_str_ids = name.split('-')[:3]
            if len(split_str_ids) > 1:
                slurm_job_name = f'{split_str_ids[1]}-{split_str_ids[2]}'
                if slurm_job_name == match_name:
                    matching_job_names.append(slurm_job_name)
        return matching_job_names

    def submit_job(self, job: Job) -> Dict[str, Any]:  # pylint: disable=too-many-locals
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

        slurm_job_name = f"{JOB_PREPEND_STR}-{job_name}-{uuid.uuid4().hex[:8]}"

        remote_job_dir = f'{self.remote_sky_dir}/{slurm_job_name}'
        remote_job_run_script = f'{remote_job_dir}/script.sh'
        slurm_utils.send_cli_command(self.ssh_client,
                                     (f"mkdir -p {remote_job_dir}; "
                                      f"touch {remote_job_run_script}; "
                                      f"chmod +x {remote_job_run_script}"))

        job_dict = {}
        #Set minimum resources that are allocatable by Slurm
        job = _override_resources(job)
        if self.compat_layer is None:
            raise ValueError(
                "No container runtime interface found on Slurm cluster.")
        submission_script = self.compat_layer.compat_method_fn(job)
        job_resources = job.spec.resources
        job_dict = {
            'name': slurm_job_name,
            'dir': remote_job_dir,
            'replicas': job.spec.replicas,
            'envs': job.spec.envs,
            'cpus': int(job_resources[ResourceEnum.CPU.value]),
            'memory': int(job_resources[ResourceEnum.MEMORY.value]),
            'gpus': int(job_resources[ResourceEnum.GPU.value]),
            'submission_script': submission_script,
        }

        dir_path = os.path.dirname(os.path.realpath(__file__))
        jinja_env = Environment(
            loader=FileSystemLoader(os.path.abspath(dir_path)),
            autoescape=select_autoescape(),
        )
        sbatch_jinja_template = jinja_env.get_template("sbatch.j2")
        sbatch_jinja = sbatch_jinja_template.render(job_dict)
        # SFTP file the over to remote server.
        with tempfile.NamedTemporaryFile(mode='w', delete=True) as file:
            file.write(sbatch_jinja)
            file.flush()
            slurm_utils.send_file_to_remote(self.ssh_client, file.name,
                                            remote_job_run_script)

        slurm_command = f"sbatch {remote_job_run_script}"
        sbatch_output, _ = slurm_utils.send_cli_command(
            self.ssh_client, slurm_command)
        slurm_job_match = re.search(r'\b\d+(?:_\d+)*\b', sbatch_output)
        if not slurm_job_match:
            raise ValueError(
                f"Failed to submit job {job_name} to Slurm cluster.")
        slurm_job_id = slurm_job_match.group(0)
        # Update cache on running job.
        self.job_cache[slurm_job_name] = slurm_job_id
        job.status.job_ids[self.name] = slurm_job_id
        return {
            "manager_job_id": slurm_job_id,
            "api_responses": [sbatch_output],
        }

    def delete_job(self, job: Job) -> Dict[str, List[str]]:
        """Deletes a Slurm job."""
        job_id: str = job.status.job_ids[self.name]
        slurm_job_id = int(job_id)
        _, stderr = slurm_utils.send_cli_command(self.ssh_client,
                                                 f'scancel {slurm_job_id}')
        if stderr:
            return {
                "api_responses": [stderr],
            }
        return {
            "api_responses": [f'Deleted job {slurm_job_id}'],
        }

    async def execute_command(  # pylint: disable=too-many-arguments
            self, websocket: WebSocket, task: str, container: str, tty: bool,
            command: List[str]):
        """Starts a tty session on the cluster."""
        raise NotImplementedError

    def get_job_logs(self, job: Job) -> List[str]:
        """Gets logs for a given job."""
        raise NotImplementedError

    def __del__(self):
        """Close SSH connection when SlurmCLIManager is deleted."""
        self.ssh_client.close()


# if __name__ == '__main__':
#     api = SlurmManagerCLI(name='sky-lab-cluster')  # 'my-slurm-cluster'
#     #print(api.get_cluster_status())
#     # Submit Job
#     from skyflow.templates import Job
#     asdf = Job()
#     asdf.metadata.name = 'hello'
#     asdf.spec.restart_policy = 'Never'
#     asdf.spec.image = 'ubuntu:latest'
#     asdf.spec.run = 'echo "Hello World"'
#     asdf.spec.replicas = 3
#     # print(api.submit_job(asdf))
#     # print(api.delete_job(asdf))
#     print(api.get_jobs_status())
