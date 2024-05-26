# pylint: disable=E1101
"""
Compatibility layer for multitiude of container management solutions.
"""
import logging
import json
import math
import os
from typing import Dict, Union

from jinja2 import Environment, FileSystemLoader, select_autoescape

from skyflow.templates import Job, ResourceEnum


class SlurmCompatiblityLayer():
    """
        Creates run scripts depending on selected/supported container manager.
    """

    def __init__(self, container_manager: str, user: str, logger=None):
        self.container_manager = container_manager
        if not container_manager:
            self.container_manager = 'no_container'
        self.user = user
        self.compat_dict = {}
        # Get all methods defined in the class
        compat_method_name = "compat_" + self.container_manager.lower()
        self.compat_method_fn = getattr(self, compat_method_name, None)
        if self.compat_method_fn is None:
            raise ValueError(f"Container manager `{self.container_manager}` not supported.")

    def create_slurm_sbatch(self, job: Job) -> str:
        """ Creates the sbatch script to send to submit with CLI.

            Args:
                Job: Job object containing job properties.

            Returns:
                Generated bash file.
        """
        #Create run script dictionary
        compat_function = "compat_" + self.container_manager.lower()
        job_dict = {}
        #Set minimum resources that are allocatable by Slurm
        job = _override_resources(job)
        submission_script = self.compat_method_fn(job)
        job_dict = self._create_job_dict(job)   
        job_dict['submission_script'] = submission_script

        import pdb; pdb.set_trace()

        env_string = ''
        for item in job_dict['envs']:
            env_string = env_string + 'export ' + item + '=' + job_dict[
                'envs'][item] + ';'
        job_dict['envs'] = env_string
        job_dict['total_mem'] = int(job.spec.resources['memory'])
        
        temp_script = job_dict['submission_script'].split('\\n')
        command_string = ''
        for command in temp_script:
            if command.startswith('#'):
                continue
            #if not command.endswith(';'):
            #command = command + ';'
            command_string = command_string + command + ';'
        command_string = command_string[:-1]
        job_dict['submission_script'] = command_string

        command = 'sbatch '
        command = command + '-c ' + str(job_dict['cpus']) + ' '
        command = command + '--mem=' + str(job_dict['total_mem']) + ' '
        if job_dict['gpus'] != 0:
            command = command + '--gpus=' + str(job_dict['gpus']) + ' '
        command = command + '--wrap=\'' + job_dict['envs'] + job_dict[
            'submission_script'] + '\' '
        return command

    def compat_no_container(self, job: Job) -> Dict[str, Union[int, str]]:
        """Generates No-Container bash script.
        
        WARNING: Does not pull images and directly runs application on the
        base OS. Do not use unless you are sure the running applications
        are safe.

            Args:
                job: Job object containing properties of submitted job.

            Returns:
                Dictionary of all the values needed for Containerd.
        """
        script_dict = {
            'shebang': '#!/bin/bash',
        }
        submission_script = _create_submission_script(script_dict)
        return submission_script

    def compat_docker(self, job: Job) -> Dict[str, Union[int, str]]:
        """ Generates Docker cli commands.

            Args:
                job: Job object containing properties of submitted job.

            Returns:
                Dictionary of all the values needed for Docker.
        """
        container_run = 'docker run '
        for value in job.spec.ports:
            container_run = container_run + '-p ' + str(value) + ' '
        if 'gpus' in job.spec.resources:
            container_run = container_run + '--gpus all '
        container_run = container_run + job.spec.image
        script_dict = {
            'shebang': '#!/bin/bash',
            'container_manager': container_run,
        }
        submission_script = _create_submission_script(script_dict)
        return submission_script

    def compat_singularity(self, job: Job) -> Dict[str, Union[int, str]]:
        """ Generates Singularity cli commands.

            Args:
                job: Job object containing properties of submitted job.

            Returns:
                Dictionary of all the values needed for Singularity.
        """
        image = ''
        if "registry.hub.docker.com" in job.spec.image:
            image = job.spec.image.split("docker.com", 1)[1]
        elif "docker://" in job.spec.image:
            image = job.spec.image
        elif "shub://" in job.spec.image:
            image = job.spec.image
        script_dict = {
            'shebang': '#!/bin/bash',
            'container_manager': 'singularity run ' + image,
        }
        submission_script = _create_submission_script(script_dict)
        return submission_script 

    def compat_containerd(self, job: Job) -> Dict[str, Union[int, str]]:
        """ Generates Containerd cli commands.

            Args:
                job: Job object containing properties of submitted job.

            Returns:
                Dictionary of all the values needed for Containerd.
        """
        containerd_ports = ''
        for value in job.spec.ports:
            containerd_ports = containerd_ports + '-p ' + str(value) + ' '
        script_dict = {
            'shebang': '#!/bin/bash',
            'container_manager': 'nerdctl run ' + job.spec.image,
            'run': job.spec.run,
        }
        submission_script = _create_submission_script(script_dict)
        if "XDG_RUNTIME_DIR" not in job.spec.envs.keys():
            job.spec.envs["XDG_RUNTIME_DIR"] = self.runtime_dir
        return submission_script
    
    def compat_podman_hpc(self, job: Job) -> Dict[str, Union[int, str]]:
        """ Generates PodmanHPC cli commands.

            Args:
                job: Job object containing properties of submitted job.

            Returns:
                Dictionary of all the values needed for Containerd.
        """
        #podman run --name basic_httpd -dt -p 8080:80/tcp docker.io/nginx
        podman_ports = ''
        for value in job.spec.ports:
            podman_ports =   podman_ports + '-p ' + str(value) + '/tcp '
        script_dict = {
            'shebang': '#!/bin/bash',
            'container_manager': 'podman-hpc run ' + job.spec.image,
            'run': job.spec.run,
        }
        submission_script = _create_submission_script(script_dict)
        return submission_script

    def compat_podman(self, job: Job) -> Dict[str, Union[int, str]]:
        """ Generates Podman cli commands.

            Args:
                job: Job object containing properties of submitted job.

            Returns:
                Dictionary of all the values needed for Containerd.
        """
        #podman run --name basic_httpd -dt -p 8080:80/tcp docker.io/nginx
        podman_ports = ''
        for value in job.spec.ports:
            podman_ports =   podman_ports + '-p ' + str(value) + '/tcp '
        script_dict = {
            'shebang': '#!/bin/bash',
            'container_manager': 'podman run -dt ' + job.spec.image,
            'run': job.spec.run,
        }
        submission_script = _create_submission_script(script_dict)
        return submission_script
    
    def compat_shifter(self, job: Job) -> Dict[str, Union[int, str]]:
        """ Generates Shifter cli commands.

            Args:
                job: Job object containing properties of submitted job.

            Returns:
                Dictionary of all the values needed for Containerd.
        """
        #shifterimg -v pull docker:image_name:latest
        raise NotImplementedError

    def _create_job_dict(self, job: Job) -> Dict[str, Union[str, int]]:
        resources = job.spec.resources
        job_dict = {
            'name': job.metadata.name,
            'envs': job.spec.envs,
            'account': self.user,
            'home': '/home',
            'cpus': int(resources['cpus']),
            'memory_per_cpu': int(resources['memory']),
            'gpus': int(resources['gpus']),
        }
        return job_dict

def _create_submission_script(script_dict, newline=True):
    """ Creates shell compatability run script based off dictionary of values.

        Args:
            Dictionary of values to append to the script.

        Returns:
            String containing the run script.

    """
    seperator = '\\n'
    if not newline:
        seperator = ';'
    submission_script = ''
    for key in script_dict:
        submission_script = submission_script + script_dict[key]
        submission_script = submission_script + seperator
    return submission_script

def _override_resources(job: Job) -> Job:
    """
        Overrides resources to fit minimum allocatable resources for Slurm.
        Arg:
            job: The job to be scheduled.
        Returns:
            Job with the corrected resources.
    """
    resources = job.spec.resources
    res_cpus = float(resources[ResourceEnum.CPU.value])
    res_memory = float(resources[ResourceEnum.MEMORY.value])
    # CPUs cannot be fractional.
    resources[ResourceEnum.CPU.value] = math.ceil(res_cpus)
    # A job must occupy at least 32 MB of memory.
    resources[ResourceEnum.MEMORY.value] = max(32, res_memory)
    job.spec.resources = resources
    return job

if __name__ == '__main__':
    job = Job()
    job.metadata.name = 'hello'
    job.spec.resources['gpus'] = 0
    job.spec.envs = {'test1':1, 'test2':2}
    sl = SlurmCompatiblityLayer(None, user='mluo')
    print(sl.create_slurm_sbatch(job))
