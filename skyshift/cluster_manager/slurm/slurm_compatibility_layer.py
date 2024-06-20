"""
Compatibility layer for multitiude of container management solutions.
"""
import logging
from typing import Dict, Union

from skyshift.templates import Job


class SlurmCompatiblityLayer():
    """
        Creates run scripts depending on selected/supported container manager.
    """

    def __init__(self, container_manager: str, user: str, logger=None):
        if not container_manager:
            self.container_manager = 'no_container'
        else:
            self.container_manager = container_manager
        self.user = user

        if not logger:
            self.logger = logging.getLogger(
                f"[{self.container_manager} - Compatibility Layer]")

        # Get all methods defined in the class
        compat_method_name = "run_" + self.container_manager.lower()
        self.compat_method_fn = getattr(self, compat_method_name, lambda x: '')
        if self.compat_method_fn is None:
            raise ValueError(
                f"Container manager `{self.container_manager}` not supported.")

    def run_no_container(self, job: Job) -> str:  # pylint: disable=no-self-use
        """Generates No-Container run commands.

        WARNING: Does not pull images and directly runs application on the
        base OS. Do not use unless you are sure the running applications
        are safe.
        """
        return job.spec.run or 'true'

    def run_docker(self, job: Job) -> str:  # pylint: disable=no-self-use
        """Generates Docker cli commands."""
        image = job.spec.image
        envs = job.spec.envs
        ports = job.spec.ports
        run_command = job.spec.run
        env_vars = ' '.join(
            [f"-e {key}={value}" for key, value in envs.items()])
        port_mappings = ' '.join([f"-p {port}:{port}" for port in ports])
        docker_command = f'''docker run \
                    {env_vars} \
                    {port_mappings} \
                    {image} \
                    {run_command}
                    '''
        return docker_command

    def run_singularity(self, job: Job) -> str:  # pylint: disable=no-self-use
        """ Generates Singularity cli commands.

            Args:
                job: Job object containing properties of submitted job.

            Returns:
                Dictionary of all the values needed for Singularity.
        """
        containerd_ports = ''
        for value in job.spec.ports:
            containerd_ports = containerd_ports + '-p ' + str(value) + ' '
        # image = ''
        # if "registry.hub.docker.com" in job.spec.image:
        #     image = job.spec.image.split("docker.com", 1)[1]
        # elif "docker://" in job.spec.image:
        #     image = job.spec.image
        # elif "shub://" in job.spec.image:
        #     image = job.spec.image
        # script_dict = {
        #     'shebang': '#!/bin/bash',
        #     'container_manager': 'singularity run ' + image,
        # }
        raise NotImplementedError

    def run_containerd(self, job: Job) -> str:  # pylint: disable=no-self-use
        """ Generates Containerd cli commands.

            Args:
                job: Job object containing properties of submitted job.

            Returns:
                Dictionary of all the values needed for Containerd.
        """
        containerd_ports = ''
        for value in job.spec.ports:
            containerd_ports = containerd_ports + '-p ' + str(value) + ' '
        # script_dict = {
        #     'shebang': '#!/bin/bash',
        #     'container_manager': 'nerdctl run ' + job.spec.image,
        #     'run': job.spec.run,
        # }
        if "XDG_RUNTIME_DIR" not in job.spec.envs.keys():
            job.spec.envs["XDG_RUNTIME_DIR"] = 'blankshots'
        raise NotImplementedError

    def run_podman_hpc(self, job: Job) -> str:  # pylint: disable=no-self-use
        """ Generates PodmanHPC run commands.

            Args:
                job: Job object containing properties of submitted job.

            Returns:
                Dictionary of all the values needed for Containerd.
        """
        #podman run --name basic_httpd -dt -p 8080:80 tcp docker.io/nginx
        podman_ports = ''
        for value in job.spec.ports:
            podman_ports = podman_ports + '-p ' + str(value) + '/tcp '
        # script_dict = {
        #     'shebang': '#!/bin/bash',
        #     'container_manager': 'podman-hpc run ' + job.spec.image,
        #     'run': job.spec.run,
        # }
        raise NotImplementedError

    def run_podman(self, job: Job) -> str:  # pylint: disable=no-self-use
        """ Generates Podman run commands."""
        #podman run --name basic_httpd -dt -p 8080:80/tcp docker.io/nginx
        podman_ports = ''
        for value in job.spec.ports:
            podman_ports = podman_ports + '-p ' + str(value) + '/tcp '
        # script_dict = {
        #     'shebang': '#!/bin/bash',
        #     'container_manager': 'podman run -dt ' + job.spec.image,
        #     'run': job.spec.run,
        # }
        raise NotImplementedError

    def run_shifter(self, job: Job) -> Dict[str, Union[int, str]]:  # pylint: disable=no-self-use
        """Generates Shifter cli commands."""
        #shifterimg -v pull docker:image_name:latest
        raise NotImplementedError


# if __name__ == '__main__':
#     job = Job()
#     job.metadata.name = 'hello'
#     job.spec.resources['gpus'] = 0
#     job.spec.envs = {'test1': 1, 'test2': 2}
#     job.spec.run = 'echo hi'
#     sl = SlurmCompatiblityLayer(None, user='mluo')
#     print(sl.create_slurm_sbatch(job))
