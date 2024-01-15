import os
import requests_unixsocket
import requests
import json
import socket
import logging
from dataclasses import dataclass
from skyflow.cluster_manager import Manager
from skyflow.templates import Job, TaskStatusEnum, AcceleratorEnum, ResourceEnum
import uuid
class SlurmAPI( object ):
    """Constructor given that environmental variables are set
    """
    def __init__ (self, slurm_port=os.environ["SLURMRESTD"], openAPI_ver=os.environ["SLURMOPENAPI"], isUnixSocket=False):
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
        #"http+unix://%2Fvar%2Flib%2Fslurm-llnl%2Fslurmrestd.socket/slurm/v0.0.36/ping")
            self.port = "http+unix://" + self.slurm_port.replace("/", "%2F")
        else:
            self.port=slurm_port
        self.port = self.port + "/slurm/" + self.openAPI_ver

    def get_status(self):
        """ Ping Slurmrestd server
        """
        fetch = self.port + "/ping"
        r = self.session.get(fetch)
        print(r.text)
    def get_node_status(self, node):
        """ Fetch status of compute node
        """
        fetch = self.port + "/node/" + node
        r = self.session.get(fetch)
        #print(r.text)
        self.__print_json(r.json())
    def __print_json(self, data):
        print(json.dumps(data, indent=4, sort_keys=True))
    def __get_json_key_val(self, data, keys):
        val = data
        for key in keys:
            try:
                val = val[key]
            except:
                return
        return val
    def send_job(self, jobFile):
        """Submit JSON job file
        """
        f = open(jobFile)
        data = json.load(f)
        post_path = self.port + "/job/submit"
        r = self.session.post(post_path, json=data)
        self.__print_json(r.json())
    def get_jobs(self):
        fetch = self.port + "/jobs"
        r = self.session.get(fetch)
        #TODO clean up relevant information
        r = r.json()
        jobCount = len(r["jobs"])
        props = (
                "name", 
                "cluster",
                "job_id", 
                "job_state"
                )
        for i in range (0, jobCount):
            print("===========Job" + str(i) + "===========")
            for prop in props:
                print(self.__get_json_key_val(r, ("jobs", i, prop)))
        #self.__print_json(r.json())
    def get_all_job_ids(self):
        fetch = self.port + "/jobs"
        r = self.session.get(fetch).json()
        jobCount = len(r["jobs"])
        job_ids = []
        for i in range (0, jobCount):
            job_ids.append(self.__get_json_key_val(r, ("jobs", i, "job_id")))
        return job_ids
    def __get_all_job_names(self):
        fetch = self.port + "/jobs"
        r = self.session.get(fetch).json()
        jobCount = len(r["jobs"])
        job_names = []
        for i in range (0, jobCount):
            job_names.append(self.__get_json_key_val(r, ("jobs", i, "name")))
        return job_names
    def get_job_resources(self):
        fetch = self.port + "/jobs"
        r = self.session.get(fetch)
        #TODO clean up relevant information
        r = r.json()
        jobCount = len(r["jobs"])
        props = (
                "allocated_cpus", 
                "cluster",
                "job_id", 
                "job_state"
                )
        for i in range (0, jobCount):
            print("===========Job" + str(i) + "===========")
            for prop in props:
                print(self.__get_json_key_val(r, ("jobs", i, prop)))
    def get_job_status(self, jobID):
        fetch = self.port + "/job/" + str(jobID)
        r = self.session.get(fetch)
        #TODO clean up relevant information
        self.__print_json(r.json())
        #print(self.__get_json_key_val(r.json(), job_id))

    def submit_job(self, job: Job) -> None:
        """
        Submit a job to the cluster, represented as a group of pods.

        This method is supposed to be idempotent. If the job has already been submitted, it does nothing.

        Args:
            job: Job object containing the JSON file.
        """
        job_name = job.get_name()
        
        # Check if the job has already been submitted.
        label_selector = f'manager=sky_manager,sky_job_id={job_name}'
        matching_workers = self.__get_all_job_names()
        if matching_workers.items:
            # Job has already been submitted.
            if matching_pods.items:
                first_object = matching_workers.items[0]
            split_str_ids = first_object.split('-')[:2]
            slurm_job_name = f'{split_str_ids[0]}-{split_str_ids[1]}'
            return {
                'manager_job_id': slurm_job_name
            }

        slurm_job_name = f'{job_name}-{uuid.uuid4().hex[:8]}'
        api_responses = []
        deploy_dict = self.__convert_to_json(job, slurm_job_name)
        response = self.send_job(job)
        api_responses.append(response)
        return {
            'manager_job_id': slrum_job_name,
            'api_responses': api_responses,
        }
    def delete_job(self, jobID):
        url = self.port + "/job/" + str(jobID)
        r = self.session.delete(url)
        #TODO clean up relevant information
        self.__print_json(r.json())

    def allocatable_resources(self) -> dict[str, dict[str, int]]:
        """ Get allocatable resources per node. """
        # Get the nodes once, then process response
        url = self.port + "/nodes/"
        r = self.session.get(url)
        r = r.json()
        numNodes = len(r["nodes"])
        available_resources = {}
        #gres for gpus, used 
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
        print(available_resources)
        return available_resources

#Slurm job definition struct
class slurm_job (object):
    def __init__ (
        script, #Run script
        account, #slurm user account name
        environment_path, #dict, Path to common dependencies 
        memory, #max memory used by job
        time_limit = 3, #job run time limit (d-hh:mm:ss)
        tasks=1, #processes in a job, tasks>1 may assign more nodes
        hold=False,
    ):
        self.script = script
        self.account = account
@dataclass
class slurm_jobs_status:
    job_id: int
    job_state: str
    err: str
    retries: int = 0
@dataclass
class slurm_job_resources:
    job_id: int
    cpus: int 
    memory: int 
    node: str 

#==================
#Testing purposes
if __name__ == "__main__":
    api = SlurmAPI(isUnixSocket=True)
    #api.get_status()
    #api.send_job('basicjob.json')
    #api.send_job('fail.json')
    #api.get_jobs()
    #api.get_job_status(37)
    #api.send_job('webserver.json')
    #api.allocatable_resources()

