"""
Defines compatability layer for generic Managers.
"""
from typing import List

from skyflow.templates import ClusterStatus, ClusterStatusEnum, Job


class ManagerException(Exception):
    """Raised when the manager is invalid."""


class Manager:
    """
    General manager object.

    Serves as the base class for the compatability layer across cluster
    managers.
    """

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

    def get_jobs_status(self):
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