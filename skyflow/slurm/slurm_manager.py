import os
import requests_unixsocket
import requests
import json
import socket
import logging
from typing import Dict, Tuple
from dataclasses import dataclass
from skyflow.cluster_manager import Manager
from skyflow.templates.cluster_template import ClusterStatus, ClusterStatusEnum
from skyflow.templates import Job, TaskStatusEnum, AcceleratorEnum, ResourceEnum
import uuid
from skyflow.slurm.slurm_utils import *
class SlurmManager( object ):
    """ Slurm compatability set for Skyflow."""

    def __init__ (self, slurm_port=os.environ["SLURMRESTD"], openAPI_ver=os.environ["SLURMOPENAPI"], isUnixSocket=True):
        """ Constructor given that environmental variables are set.
            
            Args: 
                slurm_port: unix socket or hostname slurmrestd listens on.
                openAPI_ver: openAPI version number configured on slurmrestd.
                isUnixSocket: true if its a unix socket, false if its a hostname.
            
            Raises:
                Exception: environmental variables not set, or no port or api version provided.
        """
        #Configure port depending on socket type
        if slurm_port == None:
            raise Exception("Please provide the unix port listening on, or set it in environment variable $SLURMRESTD")
            return
        if openAPI_ver == None:
            raise Exception("Please provide the openapi version slurmrestd is configured with, or set it in environment variable $SLURMOPENAPI")
            return    
        self.slurm_port = slurm_port
        self.openAPI_ver = openAPI_ver
        self.session= requests_unixsocket.Session()
        if isUnixSocket:
            self.port = "http+unix://" + self.slurm_port.replace("/", "%2F")
        else:
            self.port=slurm_port
        self.port = self.port + "/slurm/" + self.openAPI_ver

    def get_node_status(self, node) -> None:
        """ Fetches status of compute node.

            Args: slurm node name
        """
        fetch = self.port + "/node/" + node
        r = self.session.get(fetch)
        self.__print_json(r.json())
    def __print_json(self, data):
        """ DEBUG Prints json data in a readable style.
        
            Args: http response data
        """

        print(json.dumps(data, indent=4, sort_keys=True))
    def __get_json_key_val(self, data, keys: Tuple):
        """ Fetch values from nested dicts.

            Args:
                data: Json data.
                keys: Tuple of nested keys

            Returns:
                Value assoicated with last nested key

        """
        val = data
        for key in keys:
            try:
                val = val[key]
            except:
                return
        return val
    def send_job(self, jsonData):
        """Submit JSON job file

            Args: 
                jsonData: Json formatted data

            Returns:
                Response from slurmrestd
        """
        print(jsonData)
        post_path = self.port + "/job/submit"
        r = self.session.post(post_path, json=jsonData)
        self.__print_json(r.json())
        return r
    def __get_matching_job_names(self, n) -> list[str]:
        """ Gets a list of jobs with matching names. 
            
            Arg:
                n: Name of job to match against.

            Returns:
                List of all job names that match n,

        """
        fetch = self.port + "/jobs"
        r = self.session.get(fetch).json()
        jobCount = len(r["jobs"])
        job_names = []
        for i in range (0, jobCount):
            name = self.__get_json_key_val(r, ("jobs", i, "name"))
            split_str_ids = name.split('-')[:2]
            if len(split_str_ids) > 1:
                slurm_job_name = f'{split_str_ids[0]}-{split_str_ids[1]}'
                if slurm_job_name == n:
                    job_names.append(slurm_job_name)
        return job_names
    def get_job_status(self, job: Job) -> list[str]:
        """ Gets status of single job.

            Args:
                job: Job object based on Job template
            
            Returns:
                Status of job from slurmrestd
        """
        api_responses = []
        if "slurm_job_id" not in job.status.job_ids:
            api_responses.append("No slurm job ID parameter, refusing to delete")
            return api_responses
        fetch = self.port + "/job/" + str(job.status.job_ids["slurm_job_id"])
        r = self.session.get(fetch)
        #TODO clean up relevant information
        api_responses.append(r.json()[job_state])
        return api_responses
    def get_accelerator_types(self) -> Dict:
        """ Fetches accelerators available to the docker image.

            Returns: 
                Dict of accelerators
        """
        #TODO blank for now
        accelerator_types = {}
        return accelerator_types
    def cluster_resources(self) -> dict[str, dict[str, int]]:
        """ Get total resources of all nodes in the cluster. 
            
            Returns: 
                Dict of node names and a dict of their total available resources. 
        """
        # Get the nodes once, then process the response
        url = self.port + "/nodes/"
        r = self.session.get(url)
        r = r.json()
        numNodes = len(r["nodes"])
        cluster_resources = {}
        # Iterate through each node to get their resource values
        for i in range (0, numNodes):
            node_name = self.__get_json_key_val(r, ("nodes", i, "name"))
            node_cpu = self.__get_json_key_val(r, ("nodes", i, "cpus"))
            node_memory = self.__get_json_key_val(r, ("nodes", i, "real_memory"))
            #TODO GPU
            #node_gpu = self.__get_json_key_val(r, ("nodes", i, "gres"))
            node_gpu = 0
            cluster_resources[node_name] = {
                ResourceEnum.CPU.value: node_cpu,
                ResourceEnum.MEMORY.value: node_memory,
                ResourceEnum.GPU.value: node_gpu
            }
        return cluster_resources
    def allocatable_resources(self) -> dict[str, dict[str, int]]:
        """ Gets currently allocatable resources of all nodes. 
        
            Returns: 
                Dict of node names and a dict of their currently allocatable resources. 
        """
        # Get the nodes once, then process response
        url = self.port + "/nodes/"
        r = self.session.get(url)
        r = r.json()
        numNodes = len(r["nodes"])
        available_resources = {}
        # Iterate through each node to get their resource values
        for i in range (0, numNodes):
            node_name = self.__get_json_key_val(r, ("nodes", i, "name"))
            node_cpu = self.__get_json_key_val(r, ("nodes", i, "idle_cpus"))
            node_memory = self.__get_json_key_val(r, ("nodes", i, "free_memory"))
            #TODO GPU
            #node_gpu = self.__get_json_key_val(r, ("nodes", i, "gres"))
            #node_gpu_used self.__get_json_key_val(r, ("nodes", i, "gres_used"))
            node_gpu = 0
            available_resources[node_name] = {
                ResourceEnum.CPU.value: node_cpu,
                ResourceEnum.MEMORY.value: node_memory,
                ResourceEnum.GPU.value: node_gpu
            }
        return available_resources
    def get_cluster_status(self) -> ClusterStatus:
        """ Gets the cluster status by pinging slurmrestd 
        
            Returns: 
                ClusterStatus object
        """
        fetch = self.port + "/ping"
        r = self.session.get(fetch).json()
        if r["pings"][0]["ping"] != "UP" or len(r["errors"]) > 0:
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

        This method is supposed to be idempotent. If the job has already been submitted, it does nothing.

        Args:
            job: Job object containing the JSON file.
        
        Returns: 
            The submitted job name, job ID, and any job submission api responses.
        """
        job_name = job.metadata.name
        
        # Check if the job has already been submitted.
        label_selector = f'manager=sky_manager,sky_job_id={job_name}'
        current_jobs = self.__get_matching_job_names(job_name)
        #matching_workers = self.__get_all_job_names()
        if job_name in current_jobs:
            # Job has already been submitted.
            first_object = current_jobs[0]
            split_str_ids = first_object.split('-')[:2]
            slurm_job_name = f'{split_str_ids[0]}-{split_str_ids[1]}'
            print("JOB EXISTS DO NOTHING")
            return {
                'manager_job_id': slurm_job_name
            }

        slurm_job_name = f'{job_name}-{uuid.uuid4().hex[:8]}'
        api_responses = []

        #deploy_dict = self.__convert_to_json(job, slurm_job_name)
        job.metadata.name = slurm_job_name
        json = convert_yaml(job)
       
        r = self.send_job(json)
        
        api_responses.append(r)
        slurm_job_id = (r.json()["job_id"])
        return {
            'manager_job_id': slurm_job_name,
            'slurm_job_id' : slurm_job_id,
            'api_responses': api_responses,
        }
    def delete_job(self, job) -> list[str]:
        """ Deletes a job from the slurm controller. 

            Args:
                Job object to be deleted.
            Returns: 
                Any api responses
        """
        api_responses = []
        if "slurm_job_id" not in job.status.job_ids:
            api_responses.append("No slurm job ID parameter, refusing to delete")
            return api_responses
        url = self.port + "/job/" + str(job.status.job_ids["slurm_job_id"])
        r = self.session.delete(url)
        #TODO clean up relevant information
        api_responses.append(r)
        return api_responses

    def get_job_status(self) -> Dict[str, Tuple[str, str]]:
        """ Checks job status of a job within a namespaced pod.

            Returns:
                A dict of each job name mapped to status of the job
        """
        api_responses = []
        sky_manager_pods = self.core_v1.list_namespaced_pod(self.namespace, label_selector='manager=sky_manager')
        jobs_dict = {}
        for node in sky_manager_pods.items:
            sky_job_name = pod.metadata.labels['sky_job_id']
            if sky_job_name not in jobs_dict:
                jobs_dict[sky_job_name] = {}
            if pod_status not in jobs_dict[sky_job_name]:
                jobs_dict[sky_job_name][pod_status] = 0
            jobs_dict[sky_job_name][pod_status] += 1
        return jobs_dict
#Testing purposes
if __name__ == "__main__":
    api = SlurmManager(isUnixSocket=True)
    #api.get_status()
    #api.send_job('basicjob.json')
    #api.send_job('fail.json')
    #api.get_jobs()
    #api.get_job_status(37)
    #api.send_job('webserver.json')
    #api.allocatable_resources()
    #print(api.get_cluster_status())

