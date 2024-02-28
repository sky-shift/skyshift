import json
import os
import re

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from skyflow.templates import (AcceleratorEnum, ContainerEnum, Job,
                               JobStatusEnum, ResourceEnum, Service)

SUPPORTED_CONTAINER_SOLUTIONS = ["containerd", "singularity", "docker", "podman", "podmanhpc"]

class SlurmCompatiblityLayer( object ):
    
    def __init__(self, config_dict):

        #Configure manager utilized tooling
        try:
            self.container_manager = config_dict['tools']['container']
        except ConfigUndefinedError as exception:
            raise ConfigUndefinedError(
                f'Missing container manager {self.container_manager} in {SLURMRESTD_CONFIG_PATH}.'
            ) from exception   
        if self.container_manager.lower() not in SUPPORTED_CONTAINER_SOLUTIONS:
            raise ValueError(
                f'Unsupoorted container manager {self.container_manager} in {SLURMRESTD_CONFIG_PATH}.'
            ) from exception
        print(self.container_manager.upper())
        self.runtime_dir = ''
        if self.container_manager.upper() == ContainerEnum.CONTAINERD.value:
            try:
                self.runtime_dir = config_dict['tools']['runtime_dir']
            except ConfigUndefinedError as exception:
                raise ConfigUndefinedError(
                f'Missing runtime_dir for {self.container_manager} in {SLURMRESTD_CONFIG_PATH}.'
                ) from exception   
        self.compat_dict = {}
        # Get all methods defined in the class
        methods = [method for method in dir(self) if callable(getattr(self, method)) and method.startswith("compat_")]
        # Filter out methods that are not meant to be commands
        command_methods = [method for method in methods if not method.startswith("__")]
        # Add methods to the function dictionary
        for method_name in command_methods:
            self.compat_dict[method_name] = getattr(self, method_name)
        #check if supported manager
    def compat_unsupported(self):
        raise ValueError(f'Unsupported Container Manager Solution')
    def _create_submission_script(self, script_dict):
        submission_script = ''
        for key in script_dict:
            submission_script = submission_script + script_dict[key]
            submission_script = submission_script + '\\n'
        return submission_script
    def _get_envs(self, dict):
        env_list = []
        for key in dict:
            env_list.append(key + ":" + dict[key])
        return env_list
    def _create_slurm_json(self, job: Job) -> str:
        #Load jinja template
        dir_path = os.path.dirname(os.path.realpath(__file__))
        jinja_env = Environment(loader=FileSystemLoader(os.path.abspath(dir_path)),
                                autoescape=select_autoescape())
        slurm_job_template = jinja_env.get_template('slurm_job.j2')
        #Create run script dictionary
        compat_function = "compat_" + self.container_manager.lower()
        job_dict = {}
        if compat_function in self.compat_dict:
            job_dict = self.compat_dict[compat_function](job)
        else:
            self.compat_dict["compat_unsupported"]()
        
        job_jinja = slurm_job_template.render(job_dict)
        #print(job_jinja)
        json_data = json.loads(job_jinja, strict=False)
        self.print_json(json_data)
        return json_data
    def print_json(self, data):
        formatted = json.dumps(data, indent = 4)
        print(formatted)
    def compat_docker(self, job: Job):
        print("compat docker")
        #docker pull registry.hub.docker.com/library/redis
        #run_cmd = "docker run -d --name redis-stack-server -p 6379:6379 redis/redis-stack-server:latest"
        container_run = 'docker run '
        docker_ports = ''
        for value in job.spec.ports:
            container_run = container_run + '-p ' + str(value) + ' '
        if 'gpus' in job.spec.resources:
            container_run = container_run + '--gpus all ' 
        container_run = container_run + job.spec.image
        script_dict = {
            'shebang': '#!/bin/bash',
            'container_manager': container_run,
            'job_specific_script': job.spec.run,
            'footer': 'echo \'bye\''
        }
        submission_script = self._create_submission_script(script_dict)
        resources = job.spec.resources
        job_dict = {
            'submission_script': submission_script,
            'name': f'{job.metadata.name}',
            'path': f"{job.spec.envs['PATH']}",
            #'home': f"{job.spec.envs['HOME']}",
            'envs': json.dumps(job.spec.envs),
            'account': 'sub1',
            'home': '/home',
            'cpus': int(resources['cpus']),
            'memory_per_cpu':
            int(int(resources['memory']) / int(resources['cpus'])),
            'time_limit': 2400
        }
        return job_dict
    def compat_singularity(self, job: Job):
        """
        Can pull from dockerhub or singularity hub, dictated by url path

        """
        print("compat singularity")
        #singularity pull --name hello-world.simg shub://vsoch/hello-world
        #singularity shell hello-world.simg
        #singularity run shub://GodloveD/lolcow
        #singularity has no network isolation. if process binds, it is reachable

        #Convert between shub, or dockerhub
        image = ''
        if "registry.hub.docker.com" in job.spec.image:
            image = job.spec.image.split("docker.com", 1)[1]
        elif "docker://" in job.spec.image:
            image = job.spec.image
        elif "shub://" in job.spec.image:
            image = job.spec.image
        script_dict = {
            'shebang': '#!/bin/bash',
            'container_manager': 'singularity run ' + job.spec.image,
            'job_specific_script': job.spec.run,
            'footer': 'echo \'bye\''
        }
        submission_script = self._create_submission_script(script_dict)
        resources = job.spec.resources
        job_dict = {
            'submission_script': submission_script,
            'name': f'{job.metadata.name}',
            'path': f"{job.spec.envs['PATH']}",
            #'home': f"{job.spec.envs['HOME']}",
            'envs': json.dumps(job.spec.envs),
            'account': 'sub1',
            'home': '/home',
            'cpus': int(resources['cpus']),
            'memory_per_cpu':
            int(int(resources['memory']) / int(resources['cpus'])),
            'time_limit': 2400
        }
        return job_dict


    def compat_containerd(self, job: Job):
        print("compat containerd")
        containerd_ports = ''
        for value in job.spec.ports:
            containerd_ports = containerd_ports + '-p ' + str(value) + ' '
        script_dict = {
            'shebang': '#!/bin/bash',
            'container_manager': 'nerdctl run ' + job.spec.image,
            'job_specific_script': job.spec.run,
            'footer': 'echo \'bye\''
        }
        submission_script = self._create_submission_script(script_dict)
        resources = job.spec.resources
        if "XDG_RUNTIME_DIR" not in job.spec.envs.keys():
            print("set XDG")
            job.spec.envs["XDG_RUNTIME_DIR"] = self.runtime_dir
        job_dict = {
            'submission_script': submission_script,
            'name': f'{job.metadata.name}',
            'path': f"{job.spec.envs['PATH']}",
            #'home': f"{job.spec.envs['HOME']}",
            'envs': json.dumps(job.spec.envs),
            'account': 'sub1',
            'home': '/home',
            'cpus': int(resources['cpus']),
            'memory_per_cpu':
            int(int(resources['memory']) / int(resources['cpus'])),
            'time_limit': 2400
        }
        return job_dict
#if __name__ == "__main__":
    # SLURMRESTD_CONFIG_PATH = '~/.skyconf/slurmrestd.yaml'
    # absolute_path = os.path.expanduser(SLURMRESTD_CONFIG_PATH)
    # with open(absolute_path, 'r') as config_file:
    #         try:
    #             config_dict = yaml.safe_load(config_file)
    #         except ValueError as exception:
    #             raise Exception(
    #                 f'Unable to load {SLURMRESTD_CONFIG_PATH}, check if file exists.'
    #             ) from exception
    # layer = SlurmCompatiblityLayer(config_dict)
    # f = open('../../examples/redis_example.yaml')
    # mdict = yaml.safe_load(f)
    # job = Job(metadata=mdict["metadata"], spec=mdict["spec"])
    # layer._create_slurm_json(job, ContainerEnum.DOCKER)