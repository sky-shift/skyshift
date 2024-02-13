import json
import logging
import os
import socket
import uuid
from typing import Dict, Tuple, Union

import requests
import requests_unixsocket
import yaml
from jinja2 import (Environment, FileSystemLoader, PackageLoader,
                    select_autoescape)

from skyflow.cluster_manager import Manager
from skyflow.templates import (AcceleratorEnum, Job, JobStatusEnum,
                               ResourceEnum, TaskStatusEnum)
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

class ConfigUndefinedError(Exception):
    """ Raised when there is an error in slurmrestd config yaml. """
    pass


class SlurmrestdConnectionError(Exception):
    """ Raised when there is an error connecting to slurmrestd. """
    pass


class SlurmManager(Manager):
    """ Slurm compatability set for Skyflow."""

    def __init__(self):
        """ Constructor which sets up request session, and checks if slurmrestd is reachable.

            Raises:
                Exception: Unable to read config yaml from path SLURMRESTD_CONFIG_PATH.
                ConfigUndefinedError: Value required in config yaml not not defined.
        """
        is_unix_socket = False
        absolute_path = os.path.expanduser(SLURMRESTD_CONFIG_PATH)
        with open(absolute_path, 'r') as config_file:
            try:
                config_dict = yaml.safe_load(config_file)
            except:
                raise Exception('Unable to load %s', SLURMRESTD_CONFIG_PATH)
                return
            #Get openapi verision, and socket/hostname slurmrestd is listening on
            try:
                self.openapi = config_dict['slurmrestd']['openapi_ver']
            except:
                raise ConfigUndefinedError(
                    f'Define openapi in {SLURMRESTD_CONFIG_PATH}.')
                return
            try:
                self.port = config_dict['slurmrestd']['port']
            except:
                raise ConfigUndefinedError(
                    f'Define port slurmrestd is listening on in {SLURMRESTD_CONFIG_PATH}.'
                )
                return
        if 'sock' in self.port.lower():
            is_unix_socket = True

        self.session = requests_unixsocket.Session()
        if is_unix_socket:
            self.port = 'http+unix://' + self.port.replace('/', '%2F')
        self.port = self.port + '/slurm/' + self.openapi

    def _print_json(self, data: str):
        """ DEBUG Prints json data in a readable style.

            Args: http response data.
        """
        print(json.dumps(data, indent=4, sort_keys=True))

    def _get_json_key_val(self, data: str, keys: Tuple) -> str:
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
            except:
                return val
        return str(val)

    def send_job(self, json_data: str):
        """Submit JSON job file.

            Args:
                jsonData: Json formatted data.

            Returns:
                Response from slurmrestd.
        """
        post_path = self.port + '/job/submit'
        r = self.session.post(post_path, json=json_data)
        return r

    def _get_matching_job_names(self, n: str) -> list[str]:
        """ Gets a list of jobs with matching names.
        
            Arg:
                n: Name of job to match against.

            Returns:
                List of all job names that match n.

        """
        fetch = self.port + '/jobs'
        r = self.session.get(fetch).json()
        jobCount = len(r['jobs'])
        job_names = []
        for i in range(0, jobCount):
            name = self._get_json_key_val(r, ('jobs', i, 'name'))
            split_str_ids = name.split('-')[:3]
            if len(split_str_ids) > 1:
                slurm_job_name = f'{split_str_ids[1]}-{split_str_ids[2]}'
                print(slurm_job_name, "against", n)
                if slurm_job_name == n:
                    job_names.append(slurm_job_name)
        return job_names

    def _convert_to_job_json(self, job: Job) -> str:
        """ Converts job object into slurm json format.

            Args:

                job: job object to be cond verted.

            Returns:
                Json file to be submitted.
        """
        dir_path = os.path.dirname(os.path.realpath(__file__))
        jinja_env = Environment(loader=FileSystemLoader(
            os.path.abspath(dir_path)),
                                autoescape=select_autoescape())
        slurm_job_template = jinja_env.get_template('slurm_job.j2')
        image = 'hello-world'
        script_dict = {
            'shebang': '#!/bin/bash',
            'container_manager': 'nerdctl run --rm ' + image,
            'job_specific_script': 'sleep 3000',
            'footer': 'echo \'bye\''
        }
        submission_script = ''
        for key in script_dict:
            submission_script = submission_script + script_dict[key]
            submission_script = submission_script + '\\n'
        resources = job.spec.resources
        submission_script = "#!/bin/bash\\necho 'HELLO'\\nnerdctl run --rm hello-world\\nsleep 3000\\necho 'bye'"
        job_dict = {
            'submission_script': submission_script,
            'name': f'{job.metadata.name}',
            'path': '/bin',
            #'path': f"{job.spec.envs['PATH']}",
            #'home': f"{job.spec.envs['HOME']}",
            'account': 'sub1',
            'home': '/home/cdaron',
            'cpus': int(resources['cpus']),
            'memory_per_cpu':
            int(int(resources['memory']) / int(resources['cpus'])),
            'time_limit': 2400
        }
        job_jinja = slurm_job_template.render(job_dict)
        json_data = json.loads(job_jinja)
        return json_data

    def get_jobs_status(self) -> Dict[str, JobStatusEnum]:
        """ Gets status of all skyflow managed jobs.    
            Returns:
                Dict of statuses of all jobs from slurmrestd
        """
        jobs_dict: Dict[str, JobStatusEnum] = {}
        fetch = self.port + '/jobs'
        r = self.session.get(fetch).json()
        jobCount = len(r['jobs'])
        for i in range(0, jobCount):
            name = self._get_json_key_val(r, ('jobs', i, 'name'))
            split_str_ids = name.split('-')[:3]
            if len(split_str_ids) > 1:
                if split_str_ids[0] == MANAGER_NAME: #Job is Managed by skyflow
                    slurm_job_name = f'{split_str_ids[1]}-{split_str_ids[2]}'
                    state = self._get_json_key_val(r, ('jobs', i, 'job_state'))
                    job_state = self._get_job_state_enum(state)
                    jobs_dict[slurm_job_name] = job_state
        return jobs_dict
    def _get_job_state_enum(self, job_state:str) -> JobStatusEnum:
        """ Switch case to match job state to enumerated values.

            Args:
                job_state: string of job state extracted from json response.
            Returns:
                Enumeration of job status.
        """
        if job_state in SLURM_INIT:
            return JobStatusEnum.INIT
        elif job_state in SLURM_ACTIVE:
            return JobStatusEnum.ACTIVE
        elif job_state in SLURM_COMPLETE:
            return JobStatusEnum.COMPLETE
        elif job_state in SLURM_FAILED:
            return JobStatusEnum.FAILED
        else:
            return JobStatusEnum.FAILED
    def get_single_job_status(self, job:Job) -> JobStatusEnum:
        """ Gets status of a single job.

            Args:
                job: job template object containing job properties/

            Returns:
                Enumeration of job status.
        """
        if 'slurm_job_id' not in job.status.job_ids:
            return JobStatusEnum.FAILED
        fetch = self.port + '/job/' + str(job.status.job_ids['slurm_job_id'])
        r = self.session.get(fetch)
        job_state = r.json()['job_state']
        return self._get_job_state_enum(job_state)
    def get_service_status(self) -> Dict[str, Dict[str, str]]:
        return {'a': {'b': 'c'}}

    def get_accelerator_types(self) -> Dict:
        """ Fetches accelerators available to the docker image.

            Returns:
                Dict of accelerators
        """
        #TODO blank for now
        accelerator_types = {AcceleratorEnum.V100: 1}
        return accelerator_types

    def cluster_resources(self) -> Dict[str, Dict[str, int]]:
        """ Get total resources of all nodes in the cluster.

            Returns:
                Dict of node names and a dict of their total available resources.
        """
        # Get the nodes once, then process the response
        url = self.port + '/nodes/'
        r = self.session.get(url)
        r = r.json()
        numNodes = len(r['nodes'])
        cluster_resources = {}
        # Iterate through each node to get their resource values
        for i in range(0, numNodes):
            node_name = self._get_json_key_val(r, ('nodes', i, 'name'))
            node_cpu = self._get_json_key_val(r, ('nodes', i, 'cpus'))
            node_memory = self._get_json_key_val(r,
                                                 ('nodes', i, 'real_memory'))
            #TODO GPU
            #node_gpu = self._get_json_key_val(r, ('nodes', i, 'gres'))
            node_gpu = 0
            cluster_resources[node_name] = {
                ResourceEnum.CPU.value: int(node_cpu),
                ResourceEnum.MEMORY.value: int(node_memory),
                ResourceEnum.GPU.value: int(node_gpu)
            }
        return cluster_resources

    def allocatable_resources(self) -> Dict[str, Dict[str, int]]:
        """ Gets currently allocatable resources of all nodes.

            Returns:
                Dict of node names and a dict of their currently allocatable resources.
        """
        # Get the nodes once, then process response
        url = self.port + '/nodes/'
        r = self.session.get(url)
        r = r.json()
        numNodes = len(r['nodes'])
        available_resources = {}
        # Iterate through each node to get their resource values
        for i in range(0, numNodes):
            node_name = self._get_json_key_val(r, ('nodes', i, 'name'))
            node_cpu = self._get_json_key_val(r, ('nodes', i, 'idle_cpus'))
            node_memory = self._get_json_key_val(r,
                                                 ('nodes', i, 'free_memory'))
            #TODO GPU
            #node_gpu = self._get_json_key_val(r, ('nodes', i, 'gres'))
            #node_gpu_used self._get_json_key_val(r, ('nodes', i, 'gres_used'))
            node_gpu = 0
            available_resources[node_name] = {
                ResourceEnum.CPU.value: int(node_cpu),
                ResourceEnum.MEMORY.value: int(node_memory),
                ResourceEnum.GPU.value: int(node_gpu)
            }
        return available_resources

    def get_cluster_status(self) -> ClusterStatus:
        """ Gets the cluster status by pinging slurmrestd.

            Returns:
                ClusterStatus object.
        """
        HEAD_NODE = 0
        fetch = self.port + '/ping'
        r = self.session.get(fetch).json()
        if r['pings'][HEAD_NODE]['ping'] != 'UP' or len(r['errors']) > 0:
            return ClusterStatus(
                status=ClusterStatusEnum.ERROR.value,
                capacity=self.cluster_resources(),
                allocatable_capacity=self.allocatable_resources(),
            )
        return ClusterStatus(
            status=ClusterStatusEnum.READY.value,
            capacity=self.cluster_resources(),
            allocatable_capacity=self.allocatable_resources(),
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
        job_name = job.metadata.name
        # Check if the job has already been submitted.
        label_selector = f"manager=sky_manager,sky_job_id={job_name}"
        matching_jobs = self._get_matching_job_names(job_name)
        if job_name in matching_jobs:
            # Job has already been submitted.
            first_object = matching_jobs[0]
            print('JOB EXISTS DO NOTHING')
            return {'manager_job_id': first_object}

        slurm_job_name = f"{MANAGER_NAME}-{job_name}-{uuid.uuid4().hex[:8]}"
        api_responses = []

        #deploy_dict = self._convert_to_json(job, slurm_job_name)
        job.metadata.name = slurm_job_name
        json = self._convert_to_job_json(job)
        r = self.send_job(json)

        api_responses.append(r)
        slurm_job_id = (r.json()['job_id'])
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
        r = self.session.delete(url)
        #TODO clean up relevant information
        api_responses.append(r)
        return api_responses


if __name__ == '__main__':
    api = SlurmManager()
    file_path = './slurm_basic_job.json'
    file_path = "./containerdjob.json"
    with open(file_path, 'r') as json_file:
        json_data = json_file.read()
    data = json.loads(json_data)
    #print(api._print_json(api.send_job(data).json()))
    f = open('../../examples/example_simple.yaml')
    mdict = yaml.safe_load(f)
    job = Job(metadata=mdict["metadata"], spec=mdict["spec"])
    api.submit_job(job)
    #print(api.get_jobs_status())

