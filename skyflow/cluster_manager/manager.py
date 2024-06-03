"""
Defines compatability layer for generic Managers.
"""
import logging
from typing import Dict, List, Optional

from fastapi import WebSocket

from skyflow.templates import ClusterStatus, ClusterStatusEnum, Job

K8_MANAGERS = ['k8', 'kubernetes']
SLURM_MANAGERS = ['slurm']
RAY_MANAGERS = ["ray"]

SUPPORTED_CLUSTER_MANAGERS = K8_MANAGERS + SLURM_MANAGERS + RAY_MANAGERS


class ManagerException(Exception):
    """Raised when the manager is invalid."""


class Manager:
    """
    General manager object.

    Serves as the base class for the compatibility layer across cluster
    managers.
    """

    #By default, the cluster name will be the sanitized version of it.
    #This is to ensure that the cluster name is compatible with the rest of the system.
    #When the cluster name is fetched from an external source, it should be unsanitized
    #to ensure that the original name is used. This is done by the unsanitize_cluster_name function.

    def __init__(self, name: str, logger: Optional[logging.Logger] = None):
        self.cluster_name = name
        self.name = name
        self.logger = logger

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
            status=ClusterStatusEnum.INIT.value,
            capacity=self.cluster_resources,
            allocatable_capacity=self.allocatable_resources,
        )

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
