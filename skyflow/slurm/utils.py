import logging
import re
import os
import time
from typing import Dict, Tuple
import uuid
from dataclasses import dataclass

from jinja2 import Environment, select_autoescape, FileSystemLoader
from kubernetes import client, config
import yaml
import json
from skyflow.cluster_manager import Manager
from skyflow.templates import Job, TaskStatusEnum, AcceleratorEnum, ResourceEnum
@dataclass
class slurm_job_template:
    script: str
    job: Dict
    resources: Dict
def convert_yaml(job):
    slurmSubmit = {}
    scriptDict = {}

    jobDict = {}
    jobDict["name"] = job.metadata.name
    #jobDict["labels"] = job.metadata.labels
    jobDict["environment"] = job.spec.image
    jobDict["resources"] = job.spec.resources
    for key in job.spec.env:
        jobDict["environment"] = job.spec.env

    resources= job.spec.resources
    resources["mem"] = resources["memory"]
    del resources["memory"]
    jobDict["resources"] = resources
    #Check if time limit is imposed, else set as infinite
    if "time_limit" in jobDict["resources"].keys():
        jobDict["resources"]["time_limit"] = "INFINITE"

    run = job.spec.run
    
    slurmSubmit["script"] = run
    slurmSubmit["job"] = jobDict

    print(json.dumps(slurmSubmit))
    

if __name__ == "__main__":
    f = open("../../examples/example_job.yaml", "r")
    mdict = yaml.safe_load(f)
    #print(dict)
    job = Job(metadata=mdict["metadata"], spec = mdict["spec"])
    #print(dict["spec"])
    convert_yaml(job)