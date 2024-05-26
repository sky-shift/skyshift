import enum
import os
import re
from typing import Dict, List, Optional

import paramiko
import yaml

from skyflow.globals import SLURM_CONFIG_DEFAULT_PATH


class SlurmInterfaceEnum(enum.Enum):
    # Slurm supports CLI and (optional) REST API interfaces.
    REST = 'rest'
    CLI = 'cli'


def convert_slurm_block_to_dict(output: str,
                                key_name: str) -> Dict[str, Dict[str, str]]:
    """Converts Slurm list outputs into a dictionary of dictionaries."""
    final_dict = {}
    node_blocks = output.split('\n\n')
    for block in node_blocks:
        node_info = {}
        final_key = None
        lines = block.split('\n')
        for line in lines:
            # Split line by spaces, but keep key-value pairs together
            parts = re.split(r'\s+(?=\S+=)', line.strip())
            for part in parts:
                if '=' in part:
                    key, value = part.split('=', 1)
                    if key == key_name:
                        final_key = value
                    node_info[key] = value
        final_dict[final_key] = node_info
    return final_dict


def create_ssh_client(hostname: str,
                      user: str,
                      ssh_key: Optional[str] = None,
                      password: Optional[str] = None) -> paramiko.SSHClient:
    """Creates SSH client and attempts to connect to server. Raises exception if unable to connect."""
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    pkey = None
    try:
        # Connect to the SSH server
        if ssh_key:
            expanded_ssh_key = os.path.abspath(os.path.expanduser(ssh_key))
            pkey = paramiko.RSAKey.from_private_key_file(expanded_ssh_key)
        ssh_client.connect(hostname=hostname,
                           username=user,
                           pkey=pkey,
                           password=password)
    except (paramiko.AuthenticationException, paramiko.SSHException,
            paramiko.BadHostKeyException, paramiko.ChannelException) as e:
        raise e
    except Exception as e:  # pylint: disable=broad-except
        raise e
    return ssh_client


def send_file_to_remote(ssh_client: paramiko.SSHClient, local_path: str,
                        remote_path: str):
    """Sends a file to a remote cluster."""
    with ssh_client.open_sftp() as sftp:
        sftp.put(local_path, remote_path)
    sftp.close()


def send_cli_command(ssh_client: paramiko.SSHClient, command: str):
    """Seconds command locally, or through ssh to a remote cluster
        
        Args: 
            command: bash command to be run.

        Returns:
            stdout
    """
    _, stdout, stderr = ssh_client.exec_command(command)
    return stdout.read().decode().strip(), stderr.read().decode().strip()


class SlurmConfig:
    """Represents the Slurm config class. See Slurm config in `examples/slurm-config`."""

    def __init__(self, config_path: str = SLURM_CONFIG_DEFAULT_PATH):
        config_path = os.path.abspath(os.path.expanduser(config_path))
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"File '{config_path}' not found.")
        self.config_path = config_path
        self._verify_config()

    @property
    def clusters(self) -> List[str]:
        """Fetches all clusters from SlurmConfig."""
        return list(self.config.keys())

    def get_interface(self, cluster_name: str) -> str:
        """Fetches the interface type for a given cluster."""
        return self.config[cluster_name]['interface']

    def get_auth_config(self, cluster_name: str) -> dict:
        """Fetches the authentication configuration for a given cluster."""
        return self.config[cluster_name]['access_config']

    def get_ssh_client(self, cluster_name: str) -> paramiko.SSHClient:
        """Returns SSH client for a given cluster."""
        access_config = self.config[cluster_name]['access_config']
        hostname = access_config.get('hostname', None)
        user = access_config.get('user', None)
        ssh_key = access_config.get('ssh_key', None)
        password = access_config.get('password', None)
        return create_ssh_client(hostname, user, ssh_key, password)

    def _verify_config(self):
        """Verifies the Slurm configuration YAML and checks for required keys."""
        with open(self.config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        for cluster_name in self.clusters:
            cluster_dict = self.config[cluster_name]
            interface_type = cluster_dict.get('interface', None)
            if not interface_type:
                raise ValueError('Interface key not present in yaml')
            interface_type = interface_type.lower()
            if interface_type == SlurmInterfaceEnum.CLI.value:
                self._verify_cli_config(cluster_dict)
            elif interface_type == SlurmInterfaceEnum.REST.value:
                self._verify_rest_config(cluster_dict)
            else:
                raise ValueError(
                    f'Unsupported Slurm interface, {interface_type}')

    def _verify_cli_config(self, cluster_dict: dict):
        access_config = cluster_dict.get('access_config', {})
        if not access_config:
            raise ValueError('Access config not present in Slurm config.')

        hostname = access_config.get('hostname', None)
        user = access_config.get('user', None)
        if hostname is None:
            raise ValueError('Hostname not present in Slurm config.')
        if user is None:
            raise ValueError('User not present in Slurm config.')

        ssh_key = access_config.get('ssh_key', None)
        password = access_config.get('password', None)
        if ssh_key is None and password is None:
            raise ValueError(
                'Authentication secret (SSH key and/or password) is not present in Slurm config.'
            )
        elif ssh_key:
            ssh_key = os.path.abspath(os.path.expanduser(ssh_key))
            if not os.path.exists(ssh_key):
                raise FileNotFoundError(f'SSH key file {ssh_key} not found.')
        # Verify will fail other if cannot connect to Slurm login node.
        ssh_client = create_ssh_client(hostname, user, ssh_key, password)
        # Close SSH connection.
        ssh_client.close()

    def _verify_rest_config(self, cluster_dict: dict):
        raise NotImplementedError


if __name__ == '__main__':
    vf = SlurmConfig(config_path='~/slurm_config.yaml')
