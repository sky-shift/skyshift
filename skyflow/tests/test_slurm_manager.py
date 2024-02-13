import json

import pytest

from skyflow.cluster_manager.slurm_manager import SlurmManager
from skyflow.templates.job_template import Job
from skyflow.templates.resource_template import ResourceEnum
from skyflow.templates.cluster_template import ClusterStatus
manager = SlurmManager()


class TestSlurmManager:
    
    def test_init(self):
        """Tests to see if slurm manager is initialized properly"

        """
        #manager = SlurmManager()
        assert "http" in manager.port
        assert "slurm" in manager.port

    def test_get_json_key_val(self):
        #manager = SlurmManager()
        test_dict = {
            "people": {
                "jeffery": {
                    "age": 50,
                    "job": "technician"
                },
                "bob": {
                    "age:": 50
                }
            },
            "things": {}
        }
        print(test_dict["people"]["jeffery"]["age"])
        test_json = json.dumps(test_dict, indent=4)
        val = manager._get_json_key_val(test_json,
                                        ("people", "jeffery", "age"))
        assert val == test_dict["people"]["jeffery"]["age"]

    def test_send_job(self):
        dict = {
            "script": "#!/bin/bash\necho 'hi'\nsleep 3000\necho 'bye",
            "job": {
                "name": "ExampleJob",
                "account": "sub1",
                "hold": false,
                "environment": {
                    "PATH": "/bin"
                },
                "tasks": 12,
                "memory_per_cpu": 100,
                "time_limit": 240
            }
        }
        test_json = json.dumps(test_dict, indent=4)
        response = manager.send_job(test_json).json()
        assert len(response["errors"]) == 0

    def test_get_matching_jobs(self):
        #_get_matching_job_names(self, n: str) -> list[str]:
        print("None")

    def test_convert_to_job_json(self):
        #_convert_to_job_json(self, job: Job) -> str:
        print("None")

    def test_get_jobs_status(self):
        #def get_jobs_status(self, job: Job) -> str:
        print("None")

    def test_get_accelerator_types(self):
        #def get_accelerator_types(self) -> Dict:
        print("None")

    def test_cluster_resources(self):
        nodes_dict = manager.cluster_resources()
        #Iterate through node dict
        for key in values:
            assert len(key) > 0 #Node has a name
            assert type(nodes_dict[key][ResourceEnum.CPU.value]) is int
            assert type(nodes_dict[key][ResourceEnum.MEMORY.value]) is int
            assert type(nodes_dict[key][ResourceEnum.GPU.value]) is int
            #System guaranteed to have 1 cpu and 1 ram
            assert nodes_dict[key][ResourceEnum.CPU.value] > 0 
            assert nodes_dict[key][ResourceEnum.MEMORY.value] > 0      

    def test_allocatable_resources(self):
        nodes_dict = manager.cluster_resources()
        #Iterate through node dict
        for key in values:
            assert len(key) > 0 #Node has a name
            assert type(nodes_dict[key][ResourceEnum.CPU.value]) is int
            assert type(nodes_dict[key][ResourceEnum.MEMORY.value]) is int
            assert type(nodes_dict[key][ResourceEnum.GPU.value]) is int

    def test_get_cluster_status(self):
        status = manager.get_cluster_status()
        assert status.status == ClusterStatus.Enum.ERROR.value or 
            status.status == ClusterStatus.Enum.READY.value
    def test_submit_job(self):
        f = open('../../examples/example_simple.yaml')
        mdict = yaml.safe_load(f)
        job = Job(metadata=mdict["metadata"], spec=mdict["spec"])
        api.submit_job(job)
        print("None")

    def test_delete_job(self):
        f = open('../../examples/example_simple.yaml')
        mdict = yaml.safe_load(f)
        job = Job(metadata=mdict["metadata"], spec=mdict["spec"])
        print("None")
