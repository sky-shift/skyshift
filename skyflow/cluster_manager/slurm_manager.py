"""
Represents the compatability layer over Slurm native API.
"""
import json
import os
import re
import uuid
from dataclasses import dataclass
from typing import Dict, List, Tuple

import requests
import requests_unixsocket
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from skyflow.cluster_manager import Manager
from skyflow.cluster_manager.slurm_compatibility_layer import \
    SlurmCompatiblityLayer
from skyflow.templates import (AcceleratorEnum, Job, JobStatusEnum,
                               ResourceEnum, Service)
from skyflow.templates.cluster_template import ClusterStatus, ClusterStatusEnum

SLURMRESTD_CONFIG_PATH = '~/.skyconf/slurmrestd.yaml'
#Defines for job status
SLURM_ACTIVE = {'RUNNING,'
                'COMPLETING'}
SLURM_INIT = {'CONFIGURING', 'PENDING'}
SLURM_FAILED = {'FAILED', 'STOPPED', 'TIMEOUT', 'SUSPENDED', 'PREMPTED'}
SLURM_COMPLETE = {'COMPLETED'}
#Identifying Headers for job submission name
MANAGER_NAME = "skyflow:slurm"
#Slurm head node number

HEAD_NODE = 0


class ConfigUndefinedError(Exception):
    """ Raised when there is an error in slurmrestd config yaml. """


class SlurmrestdConnectionError(Exception):
    """ Raised when there is an error connecting to slurmrestd. """


@dataclass
class NodeGpus:
    num_gpus: int
    gpu_types: List[str]


class SlurmManager(Manager):
    """ Slurm compatability set for Skyflow."""

    def __init__(self):
        """ Constructor which sets up request session, and checks if slurmrestd is reachable.

            Raises:
                Exception: Unable to read config yaml from path SLURMRESTD_CONFIG_PATH.
                ConfigUndefinedError: Value required in config yaml not not defined.
        """
        super().__init__("slurm")
        is_unix_socket = False
        absolute_path = os.path.expanduser(SLURMRESTD_CONFIG_PATH)
        with open(absolute_path, 'r') as config_file:
            try:
                config_dict = yaml.safe_load(config_file)
            except ValueError as exception:
                raise Exception(
                    f'Unable to load {SLURMRESTD_CONFIG_PATH}, check if file exists.'
                ) from exception
            #Get openapi verision, and socket/hostname slurmrestd is listening on
            try:
                self.openapi = config_dict['slurmrestd']['openapi_ver']
            except ConfigUndefinedError as exception:
                raise ConfigUndefinedError(
                    f'Define openapi in {SLURMRESTD_CONFIG_PATH}.'
                ) from exception
            #Configure slurmrestd port
            try:
                self.port = config_dict['slurmrestd']['port']
            except ConfigUndefinedError as exception:
                raise ConfigUndefinedError(
                    f'Define port slurmrestd is listening on in {SLURMRESTD_CONFIG_PATH}.'
                ) from exception

        compat_layer = SlurmCompatiblityLayer(config_dict)
        if 'sock' in self.port.lower():
            is_unix_socket = True
        if is_unix_socket:
            self.session = requests_unixsocket.Session()
            self.port = 'http+unix://' + self.port.replace('/', '%2F')
        else:
            self.session = requests.Session()
            self.port = self.port
        self.port = self.port + '/slurm/' + self.openapi

        #store resource values
        self.curr_allocatable = None
        self.total_resources = None
        self.node_accelerators = self.get_gpu_config(config_dict)

    def get_gpu_config(self, config_dict):
        accelerator_types = {}
        #This one needs to be changed to gres parsing. Asymetrical nodes and clusters with hundreds-thousands of nodes cannot rely on config
        for node in config_dict:
            if "node_" in node:
                try:
                    gpus = config_dict[node]['gpus']
                except ConfigUndefinedError as exception:
                    raise ConfigUndefinedError(
                        f'Failed to process GPUs.') from exception
                gpu_arr = gpus.replace(' ', '').split(',')
                accel_list = []
                for gpu_type in gpu_arr:
                    accel_list.append(gpu_type)
                gpu_count = len(accel_list)
                if gpu_count == 0:
                    accel_list.append("None")
                node_gpu_props = NodeGpus(gpu_count, accel_list)
                accelerator_types[node] = node_gpu_props
        return accelerator_types

    def send_job(self, json_data: str):
        """Submit JSON job file.

            Args:
                jsonData: Json formatted data.

            Returns:
                Response from slurmrestd.
        """
        post_path = self.port + '/job/submit'
        response = self.session.post(post_path, json=json_data)
        return response

    def _get_matching_job_names(self, match_name: str) -> list[str]:
        """ Gets a list of jobs with matching names.

            Arg:
                match_name: Name of job to match against.

            Returns:
                List of all job names that match n.

        """
        fetch = self.port + '/jobs'
        response = self.session.get(fetch).json()
        job_count = len(response['jobs'])
        job_names = []
        for i in range(0, job_count):
            name = get_json_key_val(response, ('jobs', i, 'name'))
            split_str_ids = name.split('-')[:3]
            if len(split_str_ids) > 1:
                slurm_job_name = f'{split_str_ids[1]}-{split_str_ids[2]}'
                if slurm_job_name == match_name:
                    job_names.append(slurm_job_name)
        return job_names

    def get_jobs_status(self) -> Dict[str, JobStatusEnum]:
        """ Gets status of all skyflow managed jobs.

            Returns:
                Dict of statuses of all jobs from slurmrestd
        """
        jobs_dict: Dict[str, JobStatusEnum] = {}
        fetch = self.port + '/jobs'
        response = self.session.get(fetch).json()
        job_count = len(response['jobs'])
        for i in range(0, job_count):
            name = get_json_key_val(response, ('jobs', i, 'name'))
            split_str_ids = name.split('-')[:3]
            if len(split_str_ids) > 1:
                if split_str_ids[
                        0] == MANAGER_NAME:  #Job is Managed by skyflow
                    slurm_job_name = f'{split_str_ids[1]}-{split_str_ids[2]}'
                    state = get_json_key_val(response,
                                             ('jobs', i, 'job_state'))
                    job_state = _get_job_state_enum(state)
                    jobs_dict[slurm_job_name] = job_state
        return jobs_dict

    def get_single_job_status(self, job: Job) -> JobStatusEnum:
        """ Gets status of a single job.

            Args:
                job: job template object containing job properties/

            Returns:
                Enumeration of job status.
        """
        if 'slurm_job_id' not in job.status.job_ids:
            return JobStatusEnum.FAILED
        fetch = self.port + '/job/' + str(job.status.job_ids['slurm_job_id'])
        response = self.session.get(fetch)
        job_state = response.json()['job_state']
        return _get_job_state_enum(job_state)

    def get_service_status(self) -> Dict[str, Dict[str, str]]:
        return {'a': {'b': 'c'}}

    def get_accelerator_types(self) -> Dict[str, str]:
        """ Fetches accelerators types in each node.

            Returns:
                Dict of accelerators
        """
        url = self.port + '/nodes/'
        response = self.session.get(url).json()
        num_nodes = len(response['nodes'])
        accelerator_types = {}
        #For HPC, its safe to assume identical accelerators. Match the most appearing accelerator.
        for i in range(0, num_nodes):
            curr_node = get_json_key_val(response, ('nodes', i, 'name'))
            node_gres = get_json_key_val(response, ('nodes', i, 'gres'))
            gpu_count = 0
            if node_gres != '':  #Only if gres is configured, get available
                gpu_arr = re.findall(r'gpu:([^:]+):(\d+)', node_gres)
                most_appearing_gpu = 'None'
                num_appearing_gpu = 0
                for gpus in gpu_arr:
                    gpu_name, gpu_count = gpus
                    if int(gpu_count) > num_appearing_gpu:
                        most_appearing_gpu = gpu_name
                    accelerator_types[curr_node] = most_appearing_gpu
        return accelerator_types

    @property
    def cluster_resources(self) -> Dict[str, Dict[str, float]]:
        """ Get total resources of all nodes in the cluster.

            Returns:
                Dict of node names and a dict of their total available resources.
        """
        if self.total_resources != None:
            return self.total_resources
        # Get the nodes once, then process the response
        url = self.port + '/nodes/'
        response = self.session.get(url).json()
        num_nodes = len(response['nodes'])
        cluster_resources = {}
        # Iterate through each node to get their resource values
        for i in range(0, num_nodes):
            node_name = get_json_key_val(response, ('nodes', i, 'name'))
            node_cpu = get_json_key_val(response, ('nodes', i, 'cpus'))
            node_memory = get_json_key_val(response,
                                           ('nodes', i, 'real_memory'))
            node_gres = get_json_key_val(response, ('nodes', i, 'gres'))
            gpu_count = 0
            if node_gres != '':  #gres is configured
                gpu_arr = re.findall(r'gpu:[^:]+:(\d+)', node_gres)
                for gpus in gpu_arr:
                    gpu_count = gpu_count + int(gpus)
            cluster_resources[node_name] = {
                ResourceEnum.CPU.value: float(node_cpu),
                ResourceEnum.MEMORY.value: float(node_memory),
                ResourceEnum.GPU.value: float(gpu_count)
            }
        self.total_resources = cluster_resources
        return cluster_resources

    @property
    def allocatable_resources(self) -> Dict[str, Dict[str, float]]:
        """ Gets currently allocatable resources of all nodes.

            Returns:
                Dict of node names and a dict of their currently allocatable resources.
        """
        # Get the nodes once, then process response
        url = self.port + '/nodes/'
        response = self.session.get(url).json()
        num_nodes = len(response['nodes'])
        available_resources = {}
        # Iterate through each node to get their resource values
        for i in range(0, num_nodes):
            node_name = get_json_key_val(response, ('nodes', i, 'name'))
            allocatable_cpus = get_json_key_val(response,
                                                ('nodes', i, 'idle_cpus'))
            allocatable_memory = get_json_key_val(response,
                                                  ('nodes', i, 'free_memory'))
            node_gpu = get_json_key_val(response, ('nodes', i, 'gres_used'))
            if node_gpu == '':
                allocatable_gpus = 0
            gpu_count = 0
            if node_gres != '':  #gres is configured
                gpu_arr = re.findall(r'gpu:[^:]+:(\d+)', node_gres)
                for gpus in gpu_arr:
                    gpu_count = gpu_count + int(gpus)
            #node_gpu_used get_json_key_val(response, ('nodes', i, 'gres_used'))
            available_resources[node_name] = {
                ResourceEnum.CPU.value: float(allocatable_cpus),
                ResourceEnum.MEMORY.value: float(allocatable_memory),
                ResourceEnum.GPU.value: float(allocatable_gpus)
            }
        self.curr_allocatable = available_resources
        return available_resources

    def get_cluster_status(self) -> ClusterStatus:
        """ Gets the cluster status by pinging slurmrestd.

            Returns:
                ClusterStatus object.
        """

        fetch = self.port + '/ping'
        response = self.session.get(fetch).json()
        if response['pings'][HEAD_NODE]['ping'] != 'UP' or len(
                response['errors']) > 0:
            return ClusterStatus(
                status=ClusterStatusEnum.ERROR.value,
                capacity=self.total_resources,
                allocatable_capacity=self.curr_allocatable,
            )
        return ClusterStatus(
            status=ClusterStatusEnum.READY.value,
            capacity=self.total_resources,
            allocatable_capacity=self.curr_allocatable,
        )

    def submit_job(self, job: Job) -> Dict:
        """
        Submit a job to the cluster, represented as a group of pods.
        This method is supposed to be idempotent.
        If the job has already been submitted, it does nothing.

        Args:
            job: Job object containing the JSON file.

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

        #deploy_dict = self._convert_to_json(job, slurm_job_name)
        job.metadata.name = slurm_job_name
        json_data = _convert_to_job_json(job)
        response = self.send_job(json_data)

        api_responses.append(response)
        slurm_job_id = (response.json()['job_id'])
        #Assign slurm specific job id for future deletion search
        job.status.job_ids['slurm_job_id'] = slurm_job_id
        return {
            'manager_job_id': slurm_job_name,
            'slurm_job_id': slurm_job_id,
            'api_responses': api_responses,
        }

    def delete_job(self, job) -> list[str]:
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
        url = self.port + '/job/' + str(job.status.job_ids['slurm_job_id'])
        response = self.session.delete(url)
        api_responses.append(response)
        return api_responses

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


def get_json_key_val(data: str, keys: Tuple) -> str:
    """ Fetch values from nested dicts.

        Args:
            data: Json data.
            keys: Tuple of nested keys.

        Returns:
            Value assoicated with last nested key.

    """
    val = data
    for key in keys:
        try:
            val = val[key]
        except KeyError as exception:
            raise Exception(
                f'Key {key} does not exist in json response') from exception
    return str(val)


def _get_job_state_enum(job_state: str) -> JobStatusEnum:
    """ Switch case to match job state to enumerated values.

        Args:
            job_state: string of job state extracted from json response.
        Returns:
            Enumeration of job status.
    """
    val = JobStatusEnum.FAILED
    if job_state in SLURM_INIT:
        val = JobStatusEnum.INIT
    elif job_state in SLURM_ACTIVE:
        val = JobStatusEnum.ACTIVE
    elif job_state in SLURM_COMPLETE:
        val = JobStatusEnum.COMPLETE
    elif job_state in SLURM_FAILED:
        val = JobStatusEnum.FAILED
    return val


def _print_json(data: str):
    """ DEBUG Prints json data in a readable style.

        Args: http response data.
    """
    print(json.dumps(data, indent=4, sort_keys=True))


def _convert_to_job_json(job: Job) -> str:
    """ Converts job object into slurm json format.

        Args:

            job: job object to be cond verted.

        Returns:
            Json file to be submitted.
    """
    return compat_layer._create_slurm_json(job)


if __name__ == '__main__':
    #api = SlurmManager()
    #api.get_accelerator_types()
    #print(api.cluster_resources())
    # file_path = './slurm_basic_job.json'
    # file_path = "./containerdjob.json"
    # with open(file_path, 'r') as json_file:
    #     json_data = json_file.read()
    # data = json.loads(json_data)
    # #print(api._print_json(api.send_job(data).json()))
    # f = open('../../examples/example_simple.yaml')
    # mdict = yaml.safe_load(f)
    # job = Job(metadata=mdict["metadata"], spec=mdict["spec"])
    # api.submit_job(job)
    # #print(api.get_jobs_status())
