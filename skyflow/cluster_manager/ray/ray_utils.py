import logging
import os
import tarfile

import paramiko
from paramiko import SSHClient

from skyflow.templates.resource_template import ContainerEnum
from skyflow.utils.ssh_utils import ssh_send_command


def create_archive(directory: str, archive_name: str):
    """Create a tar archive of the directory excluding ray_manager.py."""
    with tarfile.open(archive_name, "w:gz") as tar:
        for root, _, files in os.walk(directory):
            for file in files:
                full_path = os.path.join(root, file)
                tar.add(full_path, arcname=file)


def copy_file_to_remote(ssh_client: SSHClient, local_path: str,
                        remote_path: str):
    """Copy a file from the local system to the remote system."""
    #Check if folder exists
    command = f"mkdir -p {os.path.dirname(remote_path)}"
    ssh_send_command(ssh_client, command)
    with ssh_client.open_sftp() as sftp:
        sftp.put(local_path, remote_path)


def extract_archive_on_remote(ssh_client: SSHClient, remote_dir: str,
                              remote_archive_path: str):
    """Extract the tar archive on the remote system."""
    command = f"tar xzfv {remote_archive_path} -C {remote_dir} \
        && rm -f {remote_archive_path}"

    ssh_send_command(ssh_client, command)


def copy_required_files(ssh_client: paramiko.SSHClient, remote_dir: str,
                        logger: logging.Logger):
    """Copy the required files to the remote system."""
    local_directory = os.path.dirname(os.path.realpath(__file__))
    logger.info(f"Copying files from {local_directory} to the remote system.")
    archive_name = './ray_manager_files.tar.gz'

    remote_extract_path = remote_dir
    remote_archive_path = f'{remote_extract_path}/ray_manager_files.tar.gz'
    logger.info(
        f"Copying files to {remote_extract_path} on the remote system.")

    create_archive(os.path.join(local_directory, "remote"), archive_name)
    copy_file_to_remote(ssh_client, archive_name, remote_archive_path)
    extract_archive_on_remote(ssh_client, remote_dir, remote_archive_path)

    # Clean up local archive
    os.remove(archive_name)


def find_available_container_managers(ssh_client: paramiko.SSHClient,
                                      logger: logging.Logger) -> list:
    """Check which container managers are installed and return a list of available managers."""
    available_containers = []
    for container in ContainerEnum:
        try:
            command = f"command -v {container.value.lower()}"
            output = ssh_send_command(ssh_client, command)
            if output:
                available_containers.append(container)
                logger.info(f"{container.value} is available.")
        except paramiko.SSHException as error:
            logger.error(f"Error checking for {container.value}: {error}")
    return available_containers


def get_remote_home_directory(ssh_client: paramiko.SSHClient):
    """Fetch the home directory of the remote user."""
    command = "echo $HOME"
    return ssh_send_command(ssh_client, command).strip()
