from abc import ABC, abstractmethod
from typing import Any

class TestManager(ABC):

    @abstractmethod
    def test_manager_initialization(self, docker_ssh_access_config: Any):
        pass

    @abstractmethod
    def test_manager_initialization_fail(self):
        pass

    @abstractmethod
    def test_manager_get_cluster_status(self, docker_ssh_access_config: Any):
        pass

    @abstractmethod
    def test_manager_fetch_resources_from_dashboard(self, docker_ssh_access_config: Any):
        pass

    @abstractmethod
    def test_manager_submit_job(self, docker_ssh_access_config: Any):
        pass

    @abstractmethod
    def test_manager_get_job_status(self, docker_ssh_access_config: Any):
        pass

    @abstractmethod
    def test_manager_available_resources(self, docker_ssh_access_config: Any):
        pass

    @abstractmethod
    def test_manager_logs(self, docker_ssh_access_config: Any):
        pass

    @abstractmethod
    def test_manager_delete_job(self, docker_ssh_access_config: Any):
        pass

    @abstractmethod
    def test_manager_logs_job_not_found(self, docker_ssh_access_config: Any):
        pass