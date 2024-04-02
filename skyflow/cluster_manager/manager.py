"""
Defines compatability layer for generic Managers.
"""
from typing import Dict, List

from fastapi import WebSocket

from skyflow.templates import ClusterStatus, ClusterStatusEnum, Job

SUPPORTED_CLUSTER_MANAGERS = ['k8', 'kubernetes', 'slurm']


class ManagerException(Exception):
    """Raised when the manager is invalid."""


class Manager:
    """
    General manager object.

    Serves as the base class for the compatability layer across cluster
    managers.
    """

    #By default, the cluster name will be the sanitized version of it.
    #This is to ensure that the cluster name is compatible with the rest of the system.
    #When the cluster name is fetched from an external source, it should be unsanitized
    #to ensure that the original name is used. This is done by the unsanitize_cluster_name function.

    def __init__(self, name: str):
        self.cluster_name = name

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

    def get_cluster_status(self):
        """Gets the cluster status."""
        return ClusterStatus(
            status=ClusterStatusEnum.READY.value,
            capacity=self.cluster_resources,
            allocatable_capacity=self.allocatable_resources,
        )

    def execute_command(  # pylint: disable=too-many-arguments
            self, task: str, container: str, command: List[str],
            quiet: bool) -> str:
        """Executes a command on the cluster."""
        raise NotImplementedError

    async def start_tty_session(self, websocket: WebSocket, task: str,
                                container: str, command: List[str]):
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
