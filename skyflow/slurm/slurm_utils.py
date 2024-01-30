import logging
import re
import os
import time
from typing import Dict, Tuple, List
import uuid
from dataclasses import dataclass

from jinja2 import Environment, select_autoescape, FileSystemLoader
from kubernetes import client, config
import yaml
import json
from skyflow.cluster_manager import Manager
from skyflow.templates import Job, TaskStatusEnum, AcceleratorEnum, ResourceEnum
def get_all_job_ids(self, port):
    fetch = self.port + "/jobs"
    r = self.session.get(fetch).json()
    jobCount = len(r["jobs"])
    job_ids = []
    for i in range (0, jobCount):
        job_ids.append(self.__get_json_key_val(r, ("jobs", i, "job_id")))
    return job_ids

def convert_yaml(job):
    slurmSubmit = {}
    scriptDict = {}

    jobDict = {}
    jobDict["name"] = job.metadata.name
    #jobDict["labels"] = job.metadata.labels
    #jobDict["image"] = job.spec.image
    #jobDict["resources"] = job.spec.resources
    jobDict["environment"] = job.spec.envs
    resources = job.spec.resources
    #resources["mem"] = resources["memory"]
    #del resources["memory"]
    #tasks == vCPUs
    jobDict["tasks"] = int(resources["cpus"])
    jobDict["memory_per_cpu"] = int(resources["memory"])
    #Check if time limit is imposed, else set as infinite
    if "time_limit" in jobDict.keys():
        jobDict["time_limit"] = "INFINITE"

    run = generate_containerd_slurm_run(job.spec.image, job.spec.run)
    slurmSubmit["script"] = run
    slurmSubmit["job"] = jobDict
    print("=========")
    print(json.dumps(slurmSubmit, indent=4,))
    return slurmSubmit
    
def generate_docker_slurm_run(image, runScript):
    shebang = "#!/bin/bash"
    docker_pull = "docker pull " + image
    docker_run = "docker run " + image
    cmd = shebang + "\n" + docker_pull + "\n" + docker_run + "\n" + runScript
    return cmd
def generate_containerd_slurm_run(image, runScript):
    shebang = "#!/bin/bash"
    containderd_pull = "nerdctl run --rm " + image
    cmd = shebang + "\n" + containderd_pull + "\n" + runScript
    return cmd
    
if __name__ == "__main__":
    f = open("../../examples/example_job.yaml", "r")
    mdict = yaml.safe_load(f)

    print(mdict)
    job = Job(metadata=mdict["metadata"], spec=mdict["spec"])
    #print(dict["spec"])
    print(job.spec)
    convert_yaml(job)