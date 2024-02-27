import json

import pytest

from skyflow.cluster_manager.slurm_manager import *
from skyflow.templates.cluster_template import ClusterStatus
from skyflow.templates.job_template import Job
from skyflow.templates.resource_template import ResourceEnum

manager = SlurmManager()


class TestSlurmManager:
    basic_job_dict = {
            "script": "#!/bin/bash\necho 'hi'\nsleep 5000\necho 'bye",
            "job": {
                "name": "ExampleJob",
                "account": "sub1",
                "hold": "false",
                "environment": {
                    "PATH": "/bin"
                },
                "tasks": 12,
                "memory_per_cpu": 100,
                "time_limit": 240
            }
        }
    f = open('../../examples/example_simple.yaml')
    yaml_dict = yaml.safe_load(f)
    test_job = Job(metadata=yaml_dict["metadata"], spec=yaml_dict["spec"])
    
    def test_init(self):
        """Tests to see if slurm manager is initialized properly"

        """
        #manager = SlurmManager()
        assert "http" in manager.port
        assert "slurm" in manager.port

    def test_get_json_key_val(self):
        #manager = SlurmManager()
        test_dict = {
            'people': {
                'jeffery': {
                    'age': 50,
                    'job': "technician"
                },
                'bob': {
                    'age:': 50
                }
            },
            'things': {}
        }
        #print(test_dict["people"]["jeffery"]["age"])
        test_json = json.dumps(test_dict, indent=4)
        val = get_json_key_val(test_json,
                                        ("people", "jeffery", "age"))
        assert val == str(test_dict["people"]["jeffery"]["age"])

    def test_send_job(self):

        test_json = json.dumps(self.basic_job_dict, indent=4)
        response = manager.send_job(test_json).json()
        assert len(response["errors"]) == 0
    

    def test_job_submission_pipeline(self):
        #Submit test job once
        response = manager.submit_job(self.test_job)
        assert len(response["manager_job_id"]) > 0
        assert response["slurm_job_id"] > 0

        #Check if job is in INIT, or RUNNING
        single_job_enum = manager.get_single_job_status(self.test_job)
        assert single_job_enum == JobStatusEnum.INIT or single_job_enum == JobStatusEnum.RUNNING 
        #Check if it is fetchable from all managed job dict collector
        all_managed_jobs = manager.get_jobs_status()
        found_job_flag = False
        for key in all_managed_jobs:
            if key == test_job.metadata.name:
                assert all_managed_jobs[key] == JobStatusEnum.INIT or single_job_enum == JobStatusEnum.RUNNING 
                found_job_flag = True
        assert found_job_flag
        
        #Try to resubmit identical job
        response = manager.submit_job(self.test_job)
        assert "Deny" in response["api_responses"]

        #delete the job
        response = manager.delete_job(self.test_job)
        json_response = response[0]
        assert len(response[0]["errors"]) == 0

    def test_convert_to_job_json(self):
        #_convert_to_job_json(self, job: Job) -> str:
        print("None")

    def test_get_accelerator_types(self):
        #Example slurm configuration "Gres=gpu:tesla:4,gpu:kepler:2,mps:400,bandwidth:lustre:no_consume:4G"
        #This needs to be implemented on a cluster with accelerators, or just to parse gres from restd
        #def get_accelerator_types(self) -> Dict:
        print("None")

    def test_cluster_resources(self):
        nodes_dict = manager.cluster_resources()
        #Iterate through node dict
        for key in values:
            assert len(key) > 0  #Node has a name
            assert type(nodes_dict[key][ResourceEnum.CPU.value]) is float
            assert type(nodes_dict[key][ResourceEnum.MEMORY.value]) is float
            assert type(nodes_dict[key][ResourceEnum.GPU.value]) is float
            #System guaranteed to have 1 cpu and 1 ram
            assert nodes_dict[key][ResourceEnum.CPU.value] > 0
            assert nodes_dict[key][ResourceEnum.MEMORY.value] > 0

    def test_allocatable_resources(self):
        nodes_dict = manager.cluster_resources()
        #Iterate through node dict
        for key in values:
            assert len(key) > 0  #Node has a name
            assert type(nodes_dict[key][ResourceEnum.CPU.value]) is float
            assert type(nodes_dict[key][ResourceEnum.MEMORY.value]) is float
            assert type(nodes_dict[key][ResourceEnum.GPU.value]) is float

    def test_get_cluster_status(self):
        status = manager.get_cluster_status()
        assert status.status == ClusterStatus.Enum.ERROR.value or status.status == ClusterStatus.Enum.READY.value
