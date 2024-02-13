"""
Defines compatability layer for generic Managers.
"""
from typing import Dict

from skyflow.templates import ClusterStatus, ClusterStatusEnum, Job, Service


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
        self.namespace = None

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
        return NotImplementedError

    def delete_job(self, job):
        """Deletes a managed job."""
        raise NotImplementedError

    def submit_job(self, job: Job):
        """Submits a job to the underlying cluster manager."""
        raise NotImplementedError

    def get_accelerator_types(self):
        """Gets available accelerators"""
        raise NotImplementedError

    def get_service_status(self):
        """Gets status of a service."""
        raise NotImplementedError

    def delete_service(self, service: Service):
        """Deletes a service."""
        raise NotImplementedError

    def create_or_update_service(self, service: Service):
        """Creates a service, or updates properites of existing service."""
        raise NotImplementedError

    def get_pods_with_selector(self, label_selector: Dict[str, str]):
        """Gets all pods matching a label."""
        raise NotImplementedError

    @staticmethod
    def convert_yaml(job):
        """Converts generic yaml file into manager specific format"""
        raise NotImplementedError
