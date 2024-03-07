"""
Compatibility layer for multitiude of container management solutions.
"""
import json
import os
from typing import Dict, List, Union

from jinja2 import Environment, FileSystemLoader, select_autoescape

from skyflow.templates import ContainerEnum, Job

SUPPORTED_CONTAINER_SOLUTIONS = [
    "containerd", "singularity", "docker", "podman", "podmanhpc"
]


class ConfigUndefinedError(Exception):
    """ Raised when there is an error in slurmrestd config yaml. """


class SlurmCompatiblityLayer():
    """
        Creates run scripts depending on selected/supported container manager.
    """

    def __init__(self, config_dict, config_path):
        #Configure manager utilized tooling
        try:
            self.container_manager = config_dict['tools']['container']
        except ConfigUndefinedError as exception:
            raise ConfigUndefinedError(
                f'Missing container manager {self.container_manager} in \
                {config_path}.') from exception
        if self.container_manager.lower() not in SUPPORTED_CONTAINER_SOLUTIONS:
            raise ValueError(
                f'Unsupoorted container manager {self.container_manager} in \
                    {config_path}.') from exception
        self.runtime_dir = ''
        if self.container_manager.upper() == ContainerEnum.CONTAINERD.value:
            try:
                self.runtime_dir = config_dict['tools']['runtime_dir']
            except ConfigUndefinedError as exception:
                raise ConfigUndefinedError(
                    f'Missing runtime_dir for {self.container_manager} in \
                        {config_path}.') from exception
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

    def _create_slurm_json(self, job: Job) -> str:
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
        job_jinja = slurm_job_template.render(job_dict)
        json_data = json.loads(job_jinja, strict=False)
        return json_data

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
            'footer': 'echo \'bye\''
        }
        submission_script = _create_submission_script(script_dict)
        resources = job.spec.resources
        job_dict = {
            'submission_script':
            submission_script,
            'name':
            f'{job.metadata.name}',
            'path':
            f"{job.spec.envs['PATH']}",
            'envs':
            json.dumps(job.spec.envs),
            'account':
            'sub1',
            'home':
            '/home',
            'cpus':
            int(resources['cpus']),
            'memory_per_cpu':
            int(int(resources['memory']) / int(resources['cpus'])),
            'time_limit':
            2400
        }
        return job_dict

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
            'footer': 'echo \'bye\''
        }
        submission_script = _create_submission_script(script_dict)
        resources = job.spec.resources
        job_dict = {
            'submission_script':
            submission_script,
            'name':
            f'{job.metadata.name}',
            'path':
            f"{job.spec.envs['PATH']}",
            'envs':
            json.dumps(job.spec.envs),
            'account':
            'sub1',
            'home':
            '/home',
            'cpus':
            int(resources['cpus']),
            'memory_per_cpu':
            int(int(resources['memory']) / int(resources['cpus'])),
            'time_limit':
            2400
        }
        return job_dict

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
            'footer': 'echo \'bye\''
        }
        submission_script = _create_submission_script(script_dict)
        resources = job.spec.resources
        if "XDG_RUNTIME_DIR" not in job.spec.envs.keys():
            print("set XDG")
            job.spec.envs["XDG_RUNTIME_DIR"] = self.runtime_dir
        job_dict = {
            'submission_script':
            submission_script,
            'name':
            f'{job.metadata.name}',
            'path':
            f"{job.spec.envs['PATH']}",
            'envs':
            json.dumps(job.spec.envs),
            'account':
            'sub1',
            'home':
            '/home',
            'cpus':
            int(resources['cpus']),
            'memory_per_cpu':
            int(int(resources['memory']) / int(resources['cpus'])),
            'time_limit':
            2400
        }
        return job_dict


def _create_submission_script(script_dict):
    """ Creates shell compatability run script based off dictionary of values.

        Args:
            Dictionary of values to append to the script.

        Returns:
            String containing the run script.

    """
    submission_script = ''
    for key in script_dict:
        submission_script = submission_script + script_dict[key]
        submission_script = submission_script + '\\n'
    return submission_script


def compat_unsupported():
    """ Raise an error if container manager tool is not supported by this compatibilty layer.

        Raises:
            ValueError: Provided unsupported container manager option in the config file.
    """
    raise ValueError('Unsupported Container Manager Solution')


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
