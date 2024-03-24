import json

import pytest

from skyflow.cluster_manager.slurm_manager_cli import *
from skyflow.templates.cluster_template import ClusterStatusEnum
from skyflow.templates.job_template import Job
from skyflow.templates.resource_template import ResourceEnum

manager = SlurmManagerCLI()

YAML_TEST_JOB = './slurm_testing_job.yaml'
class TestSlurmManagerCLI:

    with open(YAML_TEST_JOB) as yaml_file:
            yaml_dict = yaml.safe_load(yaml_file)
            yaml_job = Job(metadata=yaml_dict["metadata"], spec=yaml_dict["spec"])

    def test_job_submission_pipeline(self):
        """Test the whole submission, status, duplication, and deletion pipeline.

        """
        
        #Submit test job once
        response = manager.submit_job(self.yaml_job)
        assert len(response["manager_job_id"]) > 0
        assert int(response["slurm_job_id"]) > 0

        #Check if job is in a state
        all_managed_jobs = manager.get_jobs_status()
        found_job_flag = False
        for key in all_managed_jobs:
            if key == self.yaml_job.metadata.name:
                assert len(all_managed_jobs[key].value) > 0
                found_job_flag = True
        assert found_job_flag

        #Try to resubmit identical job
        response = manager.submit_job(self.yaml_job)
        assert 'Deny resubmission of identical job' in response["api_responses"]

        #delete the job
        response = manager.delete_job(self.yaml_job)
        assert 'Successfully cancelled' in response
    def pytest_exception_interact(node, call, report):
        if report.failed:
            # Run custom code when a test fails
            print("Test failed:", report.nodeid)
            response = manager.delete_job(self.yaml_job)
            # Add your custom code here
    def test_get_accelerator_types(self):
        """Test to see if we can poll for accelerator types available on each node

        """
        #Example slurm configuration "Gres=gpu:tesla:4,gpu:kepler:2,mps:400,bandwidth:lustre:no_consume:4G"
        #This needs to be implemented on a cluster with accelerators, or just to parse gres from restd
        #Because testbench or CI/CD device may not have GPUs, test if we have one node.
        node_accelerators = manager.get_accelerator_types()
        #Assert there is at least one node in the dict
        assert len(node_accelerators) > 0
        #Check for correct gres fetch and parse
        for node in node_accelerators:
            #If we have a GPU
            gres_val = node_accelerators[node].value
            assert gres_val != None


    def test_cluster_resources(self):
        """Test on fetching total cluster resources

        """
        nodes_dict = manager.cluster_resources
        #Iterate through node dict
        for key in nodes_dict:
            assert len(key) > 0  #Node has a name
            assert type(nodes_dict[key][ResourceEnum.CPU.value]) is float
            assert type(nodes_dict[key][ResourceEnum.MEMORY.value]) is float
            assert type(nodes_dict[key][ResourceEnum.GPU.value]) is float
            #System guaranteed to have 1 cpu and 1 ram
            assert nodes_dict[key][ResourceEnum.CPU.value] > 0
            assert nodes_dict[key][ResourceEnum.MEMORY.value] > 0

    def test_allocatable_resources(self):
        """Test on fetching current allocatable resources

        """
        nodes_dict = manager.allocatable_resources
        #Iterate through node dict
        for key in nodes_dict:
            assert len(key) > 0  #Node has a name
            assert type(nodes_dict[key][ResourceEnum.CPU.value]) is float
            assert type(nodes_dict[key][ResourceEnum.MEMORY.value]) is float
            assert type(nodes_dict[key][ResourceEnum.GPU.value]) is float

    def test_get_cluster_status(self):
        """Test if we can get cluster_status
        """
        status = manager.get_cluster_status()
        assert status.status == ClusterStatusEnum.ERROR.value or status.status == ClusterStatusEnum.READY.value
