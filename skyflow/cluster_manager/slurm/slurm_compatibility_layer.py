# pylint: disable=E1101
"""
Compatibility layer for multitiude of container management solutions.
"""
import json
import os
from typing import Dict, Union

from jinja2 import Environment, FileSystemLoader, select_autoescape

from skyflow.templates import Job


class ConfigUndefinedError(Exception):
    """ Raised when there is an error in slurmrestd config yaml. """


class SlurmCompatiblityLayer():
    """
        Creates run scripts depending on selected/supported container manager.
    """

    def __init__(self, container_manager, runtime_dir, time_limit,
                 slurm_account):
        self.container_manager = container_manager
        self.runtime_dir = runtime_dir
        self.time_limit = time_limit
        self.slurm_account = slurm_account
        self.compat_dict = {}
        # Get all methods defined in the class
        methods = [
            method for method in dir(self)
            if callable(getattr(self, method)) and method.startswith("compat_")
        ]
        # Filter out methods that are not meant to be commands
        command_methods = [
            method for method in methods if not method.startswith("_")
        ]
        # Add methods to the function dictionary
        for method_name in command_methods:
            self.compat_dict[method_name] = getattr(self, method_name)

    def create_slurm_json(self, job: Job) -> str:
        """ Creates the json file to send to slurmrestd.

            Args:
                Job: Job object containing job properties.

            Returns:
                Generated json that is understandable by slurmrestd.
        """
        #Load jinja template
        dir_path = os.path.dirname(os.path.realpath(__file__))
        jinja_env = Environment(loader=FileSystemLoader(
            os.path.abspath(dir_path)),
                                autoescape=select_autoescape())
        slurm_job_template = jinja_env.get_template('slurm_job.j2')
        #Create run script dictionary
        compat_function = "compat_" + self.container_manager.lower()
        job_dict = {}
        if compat_function in self.compat_dict:
            job_dict = self.compat_dict[compat_function](job)
        else:
            self.compat_dict["compat_unsupported"]()
        #Convert ENVs to json format for RESTD
        job_dict["envs"] = json.dumps(job_dict["envs"])
        job_jinja = slurm_job_template.render(job_dict)
        json_data = json.loads(job_jinja, strict=False)
        return json_data

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
        job = set_min_allocatable_resources(job)
        if compat_function in self.compat_dict:
            job_dict = self.compat_dict[compat_function](job)
        else:
            self.compat_dict["compat_unsupported"]()
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
            'job_specific_script': job.spec.run,
        }
        submission_script = _create_submission_script(script_dict)
        return self.create_job_dict(submission_script, job)

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
            'job_specific_script': job.spec.run,
        }
        submission_script = _create_submission_script(script_dict)
        return self.create_job_dict(submission_script, job)    

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
            'job_specific_script': job.spec.run,
        }
        submission_script = _create_submission_script(script_dict)
        if "XDG_RUNTIME_DIR" not in job.spec.envs.keys():
            job.spec.envs["XDG_RUNTIME_DIR"] = self.runtime_dir
        return self.create_job_dict(submission_script, job)
    
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
            'job_specific_script': job.spec.run,
        }
        submission_script = _create_submission_script(script_dict)
        return self.create_job_dict(submission_script, job)

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
            'job_specific_script': job.spec.run,
        }
        submission_script = _create_submission_script(script_dict)
        return self.create_job_dict(submission_script, job)
    
    def compat_shifter(self, job: Job) -> Dict[str, Union[int, str]]:
        """ Generates Shifter cli commands.

            Args:
                job: Job object containing properties of submitted job.

            Returns:
                Dictionary of all the values needed for Containerd.
        """
        #shifterimg -v pull docker:image_name:latest
        raise NotImplementedError
    
    def compat_nocontainer(self, job: Job) -> Dict[str, Union[int, str]]:
        """ Generates no container cli commands.

            Args:
                job: Job object containing properties of submitted job.

            Returns:
                Dictionary of all the values needed for Containerd.
        """
        script_dict = {
            'shebang': '#!/bin/bash',
            'job_specific_script': job.spec.run,
        }
        submission_script = _create_submission_script(script_dict)
        resources = job.spec.resources
        job_dict = {
            'submission_script':
            submission_script,
            'name':
            f'{job.metadata.name}',
            #'path':
            #f"{job.spec.envs['PATH']}",
            'envs':
            job.spec.envs,
            'account':
            self.slurm_account,
            'home':
            '/home',
            'cpus':
            int(resources['cpus']),
            'memory_per_cpu':
            int(int(resources['memory']) / int(resources['cpus'])),
            'gpus':
            int(resources['gpus']),
            'time_limit':
            self.time_limit
        }
        return job_dict

    def create_job_dict(self, submission_script: str, job: Job) -> Dict[str, Union[str, int]]:
        resources = job.spec.resources
        job_dict = {
            'submission_script':
            submission_script,
            'name':
            f'{job.metadata.name}',
            #'path':
            #f"{job.spec.envs['PATH']}",
            'envs':
            job.spec.envs,
            'account':
            self.slurm_account,
            'home':
            '/home',
            'cpus':
            int(resources['cpus']),
            'memory_per_cpu':
            int(int(resources['memory']) / int(resources['cpus'])),
            'gpus':
            int(resources['gpus']),
            'time_limit':
            self.time_limit
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


def compat_unsupported():
    """ Raise an error if container manager tool is not supported by this compatibilty layer.

        Raises:
            ValueError: Provided unsupported container manager option in the config file.
    """
    raise ValueError('Unsupported Container Manager Solution')

def set_min_allocatable_resources(job: Job) -> Job:
    """
        Sets the minimal amount allocatable resources that Slurm controller can allocate.
        This is a compatability function over scheduling for other managers such as Kubernetes
        where fractional CPUs can be assigned.

        Arg:
            job: The job to be scheduled.
        
        Returns: Job with the minimimal allocatable resources of Slurm
    """
    temp_job = job
    min_resources = job.spec.resources
    if int(min_resources['cpus']) < 1:
        min_resources['cpus'] = 1
    if int(min_resources['memory']) < 32:
        min_resources['memory'] = 32
    temp_job.spec.resources = min_resources
    return temp_job

if __name__ == '__main__':
    job = Job()
    job.spec.resources['gpus'] = 0
    job.spec.envs = {'test1':1, 'test2':2}
    sl = SlurmCompatiblityLayer('docker', '/home/run/1000', 900, 'mluo')
    print(sl.create_slurm_sbatch(job))
