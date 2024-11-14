"""
This module contains abstract test cases for the integration manager.
"""

from abc import ABC, abstractmethod
from typing import Any


class TestManager(ABC):
    """
    Abstract base class for testing integration managers.
    """

    @abstractmethod
    def test_manager_initialization(self, docker_ssh_access_config: Any):
        """
        Test the initialization of the manager with the given SSH access configuration.
        """
        ...

    @abstractmethod
    def test_manager_initialization_fail(self):
        """
        Test the failure scenario of manager initialization.
        """
        ...

    @abstractmethod
    def test_manager_get_cluster_status(self, docker_ssh_access_config: Any):
        """
        Test retrieving the cluster status from the manager.
        """
        ...

    @abstractmethod
    def test_manager_fetch_resources_from_dashboard(
            self, docker_ssh_access_config: Any):
        """
        Test fetching resources from the manager's dashboard.
        """
        ...

    @abstractmethod
    def test_manager_submit_job(self, docker_ssh_access_config: Any):
        """
        Test submitting a job to the manager.
        """
        ...

    @abstractmethod
    def test_manager_get_job_status(self, docker_ssh_access_config: Any):
        """
        Test retrieving the job status from the manager.
        """
        ...

    @abstractmethod
    def test_manager_available_resources(self, docker_ssh_access_config: Any):
        """
        Test fetching available resources from the manager.
        """
        ...

    @abstractmethod
    def test_manager_logs(self, docker_ssh_access_config: Any):
        """
        Test retrieving logs from the manager.
        """
        ...

    @abstractmethod
    def test_manager_delete_job(self, docker_ssh_access_config: Any):
        """
        Test deleting a job using the manager.
        """
        ...

    @abstractmethod
    def test_manager_logs_job_not_found(self, docker_ssh_access_config: Any):
        """
        Test the scenario where logs for a non-existent job are requested.
        """
        ...
