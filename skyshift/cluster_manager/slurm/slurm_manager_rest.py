# Rest API files and tests are removed for now. To be added in a future PR.
"""
Represents the compatability layer over Slurm native REST API.
"""
from typing import Dict, List

from fastapi import WebSocket

from skyshift.cluster_manager.manager import Manager
from skyshift.templates import Job


class SlurmManagerREST(Manager):
    """ Slurm Rest API compatability layer for SkyShift."""

    @property
    def cluster_resources(self):
        """
        Fetches total cluster resources.
        """
        raise NotImplementedError

    @property
    def allocatable_resources(self):
        """
        Fetches allocatable cluster resources.
        """
        raise NotImplementedError

    async def execute_command(  # pylint: disable=too-many-arguments
            self, websocket: WebSocket, task: str, container: str, tty: bool,
            command: List[str]):
        """Starts a tty session on the cluster."""
        raise NotImplementedError

    def get_jobs_status(self) -> Dict[str, Dict[str, Dict[str, str]]]:
        """Gets the status for all jobs."""
        raise NotImplementedError

    def submit_job(self, job: Job):
        """Submits a job to the underlying cluster manager."""
        raise NotImplementedError

    def delete_job(self, job: Job):
        """Deletes a job from the underlying cluster manager."""
        raise NotImplementedError

    def get_job_logs(self, job: Job) -> List[str]:
        """Gets logs for a given job."""
        raise NotImplementedError
