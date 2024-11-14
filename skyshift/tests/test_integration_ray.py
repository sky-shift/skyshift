"""
This file contains integration tests for the RayManager class.
"""
import os
import subprocess
import time
from typing import Any

import pytest

from skyshift.cluster_manager.ray.ray_manager import RayManager
from skyshift.templates import Job, ResourceEnum
from skyshift.templates.cluster_template import ClusterStatusEnum
from skyshift.templates.job_template import TaskStatusEnum
from skyshift.utils.ssh_utils import SSHConnectionError

# Fixed import error by using relative import
from .test_integration_manager import TestManager

DOCKER_IMAGE_NAME = "debian-ssh-dind"
DOCKER_CONTAINER_NAME = "debian-ssh-dind-container"
SSH_KEY_PATH = "/tmp/test_id_rsa"
SSH_PORT = 22


def run_command(command):
    """Run a shell command and return its output."""
    result = subprocess.run(command,
                            shell=True,
                            capture_output=True,
                            text=True,
                            check=True)
    if result.returncode != 0:
        raise Exception(f"Command failed: {command}\n{result.stderr}")
    return result.stdout


@pytest.fixture(scope="session", autouse=True)
def setup_docker_container():
    """Setup a Docker container for testing."""
    # Step 1: Create Dockerfile content
    dockerfile_content = '''
    FROM debian:latest

    # Install necessary packages
    RUN apt-get update && apt-get install -y \
        openssh-server \
        sudo \
        apt-transport-https \
        ca-certificates \
        curl \
        gnupg \
        lsb-release

    # Install Docker
    RUN curl -fsSL https://download.docker.com/linux/debian/gpg | \
        gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    RUN echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] \
        https://download.docker.com/linux/debian $(lsb_release -cs) \
            stable" > /etc/apt/sources.list.d/docker.list
    RUN apt-get update && apt-get install -y docker-ce docker-ce-cli containerd.io

    # Create a new user and add to the Docker group
    RUN useradd -m -s /bin/bash dockeruser && echo "dockeruser:dockeruser" | \
        chpasswd && adduser dockeruser sudo && usermod -aG docker dockeruser

    # Setup SSH for the new user
    RUN mkdir /var/run/sshd && \
        sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config && \
        sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config && \
        sed -i 's/UsePAM yes/UsePAM no/' /etc/ssh/sshd_config && \
        mkdir -p /home/dockeruser/.ssh && chmod 700 /home/dockeruser/.ssh && \
            chown dockeruser:dockeruser /home/dockeruser/.ssh

    # Expose ports
    EXPOSE 22
    EXPOSE 2375
    EXPOSE 10001
    EXPOSE 8265
    EXPOSE 6379

    # Start Docker daemon and SSH
    CMD dockerd-entrypoint.sh & /usr/sbin/sshd -D
    '''

    # Step 2: Write Dockerfile to temporary location
    with open("/tmp/Dockerfile", "w") as dockerfile:
        dockerfile.write(dockerfile_content)

    # Step 3: Build Docker image
    run_command(f"docker build -t {DOCKER_IMAGE_NAME} -f /tmp/Dockerfile /tmp")

    # Step 4: Run Docker container with resource limits
    run_command(f"docker run -d -p {SSH_PORT}:22 -p 2375:2375 -p 10001:10001\
                 -v /var/run/docker.sock:/var/run/docker.sock \
                 -p 8265:8265 -p 6379:6379 --name {DOCKER_CONTAINER_NAME} \
                 --memory=3g --cpus=1  {DOCKER_IMAGE_NAME}")

    # Step 5: Generate SSH key pair
    run_command(f"ssh-keygen -t rsa -f {SSH_KEY_PATH} -q -N ''")

    # Step 6: Manually copy public key to Docker container
    with open(f"{SSH_KEY_PATH}.pub", "r") as pubkey_file:
        pubkey_contents = pubkey_file.read().strip()

    run_command(
        f"docker exec {DOCKER_CONTAINER_NAME} bash -c 'chmod 0777 /var/run/docker.sock'"
    )  # pylint: disable=line-too-long
    run_command(
        f"docker exec {DOCKER_CONTAINER_NAME} bash -c 'echo \"{pubkey_contents}\" > /home/dockeruser/.ssh/authorized_keys'"
    )  # pylint: disable=line-too-long
    run_command(
        f"docker exec {DOCKER_CONTAINER_NAME} bash -c 'chmod 600 /home/dockeruser/.ssh/authorized_keys && chown dockeruser:dockeruser /home/dockeruser/.ssh/authorized_keys'"
    )  # pylint: disable=line-too-long

    # Step 7: Change permissions of the private key
    os.chmod(SSH_KEY_PATH, 0o600)

    # Allow some time for the container to fully start
    time.sleep(5)

    # Verify SSH connection manually
    try:
        run_command(
            f"ssh -i {SSH_KEY_PATH} -o StrictHostKeyChecking=no -p {SSH_PORT} dockeruser@localhost echo 'SSH connection successful'"
        )
    except SSHConnectionError as error:
        raise Exception(
            f"Failed to establish SSH connection: {error}") from error

    yield

    # Cleanup after tests
    run_command(f"docker stop {DOCKER_CONTAINER_NAME}")
    run_command(f"docker rm {DOCKER_CONTAINER_NAME}")
    run_command(f"docker rmi {DOCKER_IMAGE_NAME}")
    os.remove("/tmp/Dockerfile")
    os.remove(SSH_KEY_PATH)
    os.remove(f"{SSH_KEY_PATH}.pub")


@pytest.fixture(scope="session")
def docker_ssh_access_config():
    """Provide Docker SSH access configuration."""
    return {
        "ssh_key_path": SSH_KEY_PATH,
        "username": "dockeruser",
        "host": "localhost",
        "port": SSH_PORT
    }


class TestRayManager(TestManager):
    """Test suite for RayManager."""

    @staticmethod
    def test_manager_initialization(_: Any):
        """
        Test the initialization of the RayManager.
        """
        ray_manager = RayManager("test", docker_ssh_access_config())
        assert ray_manager.client is not None

    @staticmethod
    def test_manager_get_cluster_status(_: Any):
        """
        Test retrieving the cluster status from the RayManager.
        """
        ray_manager = RayManager("test", docker_ssh_access_config())
        cluster_status = ray_manager.get_cluster_status()
        assert cluster_status.status == ClusterStatusEnum.READY.value

    @staticmethod
    def test_manager_fetch_resources_from_dashboard(_: Any):
        """
        Test fetching resources from the Ray dashboard.
        """
        ray_manager = RayManager("test", docker_ssh_access_config())
        resources = ray_manager.fetch_resources_from_dashboard(usage=False)
        assert isinstance(resources, dict)
        expected_output = {
            ResourceEnum.CPU.value: 1,
            ResourceEnum.DISK.value: 512,
        }
        for node_id in resources:
            for res in expected_output:
                assert resources[node_id].get(res) == expected_output[res]

    @staticmethod
    def test_manager_submit_job(_: Any):
        """
        Test job submission to the RayManager.
        """
        ray_manager = RayManager("test", docker_ssh_access_config())
        job = Job()
        job.spec = type('spec', (object, ), {})()  # Create a spec object
        job.spec.resources = {
            ResourceEnum.CPU.value: 0.5,
            ResourceEnum.MEMORY.value: 128
        }
        job.spec.image = "nginx"
        job.metadata = type('metadata', (object, ),
                            {})()  # Create a metadata object
        job.metadata.name = "job121"
        job.metadata.namespace = "default"

        submission_details = ray_manager.submit_job(job)
        time.sleep(5)
        assert 'job121-default' in submission_details["manager_job_id"]

    @staticmethod
    def test_manager_get_job_status(_: Any):
        """
        Test retrieving the job status from the RayManager.
        """
        ray_manager = RayManager("test", docker_ssh_access_config())
        job_status = ray_manager.get_jobs_status()
        assert isinstance(job_status, dict)
        assert len(job_status["tasks"].items()) > 0
        for tasks in job_status["tasks"].values():
            assert tasks["job121"] == TaskStatusEnum.RUNNING.value

    @staticmethod
    def test_manager_available_resources(_: Any):
        """
        Test fetching available resources from the Ray dashboard.
        """
        ray_manager = RayManager("test", docker_ssh_access_config())
        resources = ray_manager.fetch_resources_from_dashboard(usage=True)
        assert isinstance(resources, dict)
        for node_id in resources:
            assert resources[node_id][ResourceEnum.CPU.value] > 0
            assert resources[node_id][ResourceEnum.CPU.value] < 0.6

    @staticmethod
    def test_manager_logs(_: Any):
        """
        Test retrieving logs for a job from the RayManager.
        """
        ray_manager = RayManager("test", docker_ssh_access_config())
        job = Job()
        job.status = type('status', (object, ), {})()  # Create a status object
        job.status.job_ids = {"test": "job121-default-SkyShift"}
        logs = ray_manager.get_job_logs(job)
        assert any("nginx" in log.lower() for log in logs)

    @staticmethod
    def test_manager_delete_job(_: Any):
        """
        Test deleting a job using the RayManager.
        """
        ray_manager = RayManager("test", docker_ssh_access_config())
        job = Job()
        job.status = type('status', (object, ), {})()  # Create a status object
        job.status.job_ids = {"test": "job121-default-SkyShift"}
        ray_manager.delete_job(job)
        time.sleep(5)
        job_status = ray_manager.get_jobs_status()
        assert isinstance(job_status, dict)
        for tasks in job_status["tasks"].values():
            assert tasks["job121"] == TaskStatusEnum.DELETED.value

    @staticmethod
    def test_manager_logs_job_not_found(_: Any):
        """
        Test retrieving logs for a non-existent job from the RayManager.
        """
        ray_manager = RayManager("test", docker_ssh_access_config())
        job = Job()
        job.metadata = type('metadata', (object, ),
                            {})()  # Create a metadata object
        job.metadata.name = "job121"
        job.status = type('status', (object, ), {})()  # Create a status object
        job.status.job_ids = {"test": "jobnotfound-default-SkyShift"}
        logs = ray_manager.get_job_logs(job)
        assert logs == []
