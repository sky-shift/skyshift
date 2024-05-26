"""
SSH utility functions for connecting to remote hosts.
"""
import enum
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import paramiko
from paramiko.config import SSHConfig

from skyflow.globals import SKYCONF_DIR, USER_SSH_PATH

# Constants
DEFAULT_SSH_CONFIG_PATH = os.path.join(USER_SSH_PATH, "config")
PARAMIKO_LOG_PATH = os.path.join(SKYCONF_DIR, "paramiko.log")
SSH_LOG_DIR = os.path.join(SKYCONF_DIR, '.ssh')
SSH_LOG = os.path.join(SSH_LOG_DIR, 'skyflow_ssh_config.log')

# Logging setup
paramiko.util.log_to_file(os.path.expanduser(PARAMIKO_LOG_PATH))
logging.basicConfig(
    level=logging.INFO,
    format="%(name)s - %(asctime)s - %(levelname)s - %(message)s")

logging.getLogger("paramiko").setLevel(logging.INFO)


class SSHConfigNotDefinedError(Exception):
    """Raised when there is an error in SSH config."""

    def __init__(self, variable_name: str) -> None:
        super().__init__(f"Variable '{variable_name}' is not provided")
        self.variable_name = variable_name


class SSHConnectionError(Exception):
    """Raised when there is an error establishing SSH connection."""


class SSHStatusEnum(enum.Enum):
    """Remote SSH host reachability enum"""
    REACHABLE = True
    NOT_REACHABLE = False


@dataclass
class SSHParams:
    """SSH connection parameters"""
    remote_hostname: str
    remote_username: str
    rsa_key: Optional[str] = None
    passkey: Optional[str] = None
    uses_passkey: bool = False
    port: int = 22


@dataclass
class SCPStruct:
    """SCP Client struct for status and SCP client"""
    status: SSHStatusEnum
    # scp_client: Optional[SCPClient] = None


@dataclass
class SSHStruct:
    """SSH Client struct for status and SSH client"""
    status: SSHStatusEnum
    ssh_client: Optional[paramiko.SSHClient] = None


def log_ssh_status(msg: str) -> None:
    """Logging utility"""
    os.makedirs(SSH_LOG_DIR, exist_ok=True)
    try:
        with open(SSH_LOG, 'a') as file:
            file.write(msg + '\n')  # Append content to the file
    except OSError as error:
        logging.error("Error appending to file '%s': %s", SSH_LOG, error)


def read_ssh_config(
        host_entry: str,
        config_path: str = DEFAULT_SSH_CONFIG_PATH) -> Dict[str, Any]:
    """
    Read SSH config from ssh_config file.
    This assumes pubkey is copied to the remote host, and the pubkey is in the ~/.ssh directory.
    """
    absolute_path = os.path.abspath(os.path.expanduser(config_path))
    config = SSHConfig.from_path(absolute_path)
    host_config = config.lookup(host_entry)
    logging.debug("Host config for '%s': %s", host_entry, host_config)
    return host_config


def read_and_connect_from_config(
        host_entry: str,
        config_path: str = DEFAULT_SSH_CONFIG_PATH) -> paramiko.SSHClient:
    """
    Uses ssh config file to read entries and connect clients
    """
    ssh_client = paramiko.SSHClient()
    host_config = read_ssh_config(host_entry, config_path)
    ssh_client.load_system_host_keys()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh_client.connect(hostname=host_config['hostname'],
                           port=int(host_config.get('port', 22)),
                           username=host_config['user'],
                           key_filename=host_config.get('identityfile', None),
                           look_for_keys=host_config.get(
                               'identitiesonly', 'yes').lower()
                           in ['yes', 'true'])
    except paramiko.ssh_exception.SSHException as error:
        logging.error("SSH connection setup failed: %s", error)
        raise SSHConnectionError(
            f"SSH connection setup failed: {error}") from error

    return ssh_client


def read_and_connect_list_from_config(
    host_entries: List[str],
    config_file: str = DEFAULT_SSH_CONFIG_PATH
) -> Dict[str, paramiko.SSHClient]:
    """
    Uses ssh config file to read entries and connect all clients.
    Args:
        host_entries: List of hostnames in ssh configuration file.
    Returns:
        Dict of all hostnames and clients.
    """
    ssh_clients: Dict[str, paramiko.SSHClient] = {}
    for host in host_entries:
        ssh_clients[host] = read_and_connect_from_config(host, config_file)
    return ssh_clients


def get_host_entries(config_path: str = DEFAULT_SSH_CONFIG_PATH) -> set[str]:
    """
    Returns all hosts configured in SSH config file.
    Return:
        List of host entries in ssh configuration file.
    """
    absolute_path = os.path.abspath(os.path.expanduser(config_path))
    # Load SSH config file
    config = SSHConfig()
    with open(absolute_path) as file:
        config.parse(file)
    return config.get_hostnames()


def create_all_ssh_clients(
        config_path: str = DEFAULT_SSH_CONFIG_PATH
) -> List[paramiko.SSHClient]:
    """
    Creates list of SSHClient objects from ssh config file.
    Arg:
        config_path: ssh configuration file path.
    Returns:
        List containing all open ssh_clients.
    """
    hosts = get_host_entries(config_path)
    ssh_clients: List[paramiko.SSHClient] = []
    for host in hosts:
        ssh_clients.append(read_and_connect_from_config(host, config_path))
    return ssh_clients


def check_reachable(ssh_params: SSHParams) -> SSHStruct:
    """
    Sanity check to make sure login node is reachable via SSH.
    Args:
        ssh_params: dataclass which includes necessary information to establish SSH connection.
    Returns:
        Whether remote host is reachable or not.
    """
    return connect_ssh_client(ssh_params)


def load_private_key(ssh_key_path: str) -> paramiko.RSAKey:
    """Load RSA private key from file."""
    key_file_path = os.path.abspath(os.path.expanduser(ssh_key_path))
    if not os.path.exists(key_file_path):
        raise FileNotFoundError(f"SSH key file not found: {ssh_key_path}")
    return paramiko.RSAKey.from_private_key_file(key_file_path)


def connect_ssh_client(ssh_params: SSHParams) -> SSHStruct:
    """
    Connects the client and returns a struct containing the status and ssh client.
    Args:
        ssh_params: Parameters required for connecting to remote host.
    Returns:
        SSHStruct
    """
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    reachability_flag = True

    try:
        if ssh_params.uses_passkey:
            ssh_client.connect(hostname=ssh_params.remote_hostname,
                               username=ssh_params.remote_username,
                               password=ssh_params.passkey)
        else:
            ssh_client.connect(hostname=ssh_params.remote_hostname,
                               username=ssh_params.remote_username,
                               pkey=load_private_key(ssh_params.rsa_key)
                               if ssh_params.rsa_key else None)
        logging.info(
            "Host: %s@%s reachable",
            ssh_params.remote_hostname,
            ssh_params.remote_username,
        )
    except paramiko.AuthenticationException:
        logging.error(
            'Unable to authenticate user, please check configuration')
        reachability_flag = False
    except paramiko.SSHException:
        logging.error(
            'SSH protocol negotiation failed, please check if remote server is reachable'
        )
        reachability_flag = False
    except Exception as error:  # pylint: disable=broad-except
        logging.error("Unexpected exception: %s", error)
        reachability_flag = False

    return SSHStruct(status=SSHStatusEnum.REACHABLE
                     if reachability_flag else SSHStatusEnum.NOT_REACHABLE,
                     ssh_client=ssh_client)


def create_ssh_client(ssh_params: SSHParams) -> paramiko.SSHClient:
    """
    Connects and returns SSH client object.
    This is assuming you are certain the remote host is reachable.
    Args:
        ssh_params: dataclass which includes necessary information to establish SSH connection.
    Returns:
        Paramiko SSH client object
    """
    ssh_struct = connect_ssh_client(ssh_params)
    if ssh_struct.ssh_client is None:
        raise SSHConnectionError("SSH client connection failed")
    return ssh_struct.ssh_client


def verify_ssh_client(ssh_params: SSHParams) -> SSHStatusEnum:
    """
    Sanity check to make sure remote host is reachable, and returns the connected SSHClient object.
    Closes the connection afterwards.
    Args:
        ssh_params: struct of information needed to establish an SSH connection.
    Returns:
        SSH connection success status
    """
    ssh_struct = connect_ssh_client(ssh_params)
    if ssh_struct.status == SSHStatusEnum.REACHABLE and ssh_struct.ssh_client is not None:
        ssh_struct.ssh_client.close()
    return ssh_struct.status


def ssh_send_command(ssh_client: paramiko.SSHClient, command: str) -> str:
    """Sends command to remote machine over ssh pipe"""
    _, stdout, _ = ssh_client.exec_command(command)
    return stdout.read().decode().strip()


if __name__ == '__main__':
    print(read_ssh_config('mac'))
    print(get_host_entries())

    # client = create_ssh_client(ssh_params)
    # sftp_client = connect_sftp_client(ssh_params)
    print('done')
    # send_scp_async(sftp_client, file_dict)
