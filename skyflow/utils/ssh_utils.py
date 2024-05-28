"""
Utils file containing functions for widely used SSH operations. 
"""
import enum
import logging
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import paramiko
from paramiko.config import SSHConfig

from skyflow.globals import SKYCONF_DIR

DEFAULT_SSH_CONFIG_PATH = '~/.ssh/config'
PARAMIKO_LOG_PATH = '~/.skyconf/paramiko.log'
paramiko.util.log_to_file(os.path.expanduser(PARAMIKO_LOG_PATH))

logging.basicConfig(
    level=logging.INFO,
    format="%(name)s - %(asctime)s - %(levelname)s - %(message)s")


class SSHConfigNotDefinedError(Exception):
    """ Raised when there is an error in slurm config yaml. """

    def __init__(self, variable_name):
        self.variable_name = variable_name
        super().__init__(f"Variable '{variable_name}' is not provided")


class SSHConnectionError(Exception):
    """ Raised when there is an error establishing SSH connection to slurm cluster. """


SSH_LOG_DIR = SKYCONF_DIR + '/.ssh/'
SSH_LOG = SSH_LOG_DIR + 'skyflow_ssh_config.log'


@dataclass
class SSHParams():
    remote_hostname: str
    remote_username: str
    rsa_key: str
    passkey: str
    uses_passkey: bool = False
    port: int = 22

    def __init__(self,
                 remote_hostname=None,
                 remote_username=None,
                 rsa_key=None,
                 passkey=None,
                 uses_passkey=False,
                 port=22):
        self.remote_hostname = remote_hostname
        self.remote_username = remote_username
        self.rsa_key = rsa_key
        self.passkey = passkey
        self.uses_passkey = uses_passkey
        self.port = port


class SSHStatusEnum(enum.Enum):
    """Remote SSH host reachability enum"""
    REACHABLE = True
    NOT_REACHABLE = False


@dataclass
class SSHStruct():
    """SSH Client struct for status and ssh client"""
    status: SSHStatusEnum
    ssh_client: paramiko.SSHClient

    def __init__(self, status=SSHStatusEnum.NOT_REACHABLE, ssh_client=None):
        self.status = status
        self.ssh_client = ssh_client


def log_ssh_status(msg):
    """ 
        Logging Utility
        Arg:
            msg: String to be logged.
    """
    if not os.path.exists(SSH_LOG_DIR):
        logging.info(f"Creating directory '{SSH_LOG_DIR}'")
        os.makedirs(Path(SSH_LOG_DIR))
    if not os.path.exists(SSH_LOG):
        try:
            logging.info(f"Creating log file '{SSH_LOG}'")
            with open(SSH_LOG, 'w'):
                pass
        except OSError as e:
            logging.info(f"Error creating file '{SSH_LOG}'")
    try:
        with open(SSH_LOG, 'a') as file:
            file.write(msg + '\n')  # Append content to the file
    except OSError as e:
        logging.info(f"Error appending to file '{SSH_LOG}'")


def read_ssh_config(host_entry, config_path=DEFAULT_SSH_CONFIG_PATH):
    """
        Read SSH config from ssh_config file. 
        This assumes pubkey is copied to the remote host, and the pubkey is in the ~/.ssh directory
    """
    absolute_path = os.path.abspath(os.path.expanduser(config_path))
    config = SSHConfig.from_path(absolute_path)
    host_config = config.lookup(host_entry)
    print(host_config)
    return host_config


def read_and_connect_from_config(host_entry: str,
                                 config_path=DEFAULT_SSH_CONFIG_PATH):
    """
        Uses ssh config file to read entries and connect clients
    """
    ssh_client = paramiko.SSHClient()
    host_config = paramiko.SSHConfigDict = read_ssh_config(
        host_entry, config_path)
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
        logging.error(f"SSH connection setup failed: {error}")
        raise error
    return ssh_client


def load_private_key(key_path: str):
    """
        Loads private key from file.
    """
    try:
        with open(os.path.abspath(os.path.expanduser(key_path)),
                  "r") as key_file:
            private_key = paramiko.RSAKey.from_private_key(key_file)
    except paramiko.ssh_exception.PasswordRequiredException as error:
        logging.error(f"Private key password required: {error}")
        raise error
    except paramiko.ssh_exception.SSHException as error:
        logging.error(f"Private key error: {error}")
        raise error
    return private_key


def connect_from_args(hostname: str,
                      private_key_file: str,
                      username: str,
                      port=22):
    """
        Connects to remote host using provided arguments.
    """
    ssh_client = paramiko.SSHClient()
    ssh_client.load_system_host_keys()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh_client.connect(hostname=hostname,
                           port=port,
                           username=username,
                           pkey=load_private_key(private_key_file))
    except paramiko.ssh_exception.SSHException as error:
        logging.error(f"SSH connection setup failed: {error}")
        raise error
    return ssh_client


def read_and_connect_list_from_config(
        host_entries: List[str],
        config_file=DEFAULT_SSH_CONFIG_PATH) -> Dict[str, paramiko.SSHClient]:
    """
        Uses ssh config file to read entries and connect all clients.
        Args:
            host_entries: List of hostnames in ssh configuration file.
        Returns:
            Dict of all hostnamnes and clients.
    """
    ssh_clients = {}
    for host in host_entries:
        ssh_client = read_and_connect_from_config(host, config_file)
        ssh_clients[host] = ssh_client
    return ssh_clients


def get_host_entries(config_path=DEFAULT_SSH_CONFIG_PATH) -> List[str]:
    """
        Returns all hosts configured in SSH config file
        Return:
            List of host entries in ssh configuration file.
    """
    absolute_path = os.path.abspath(os.path.expanduser(config_path))
    # Load SSH config file
    config = SSHConfig()
    with open(absolute_path) as f:
        config.parse(f)
    return (config.get_hostnames())


def create_all_ssh_clients(config_path=DEFAULT_SSH_CONFIG_PATH):
    """
        Creates list of SSHClient objects from ssh config file.
        Arg:
            config_path:
                ssh configuration file path.
        Returns:    
            List containing all open ssh_clients.
    """
    hosts = get_host_entries(config_path)
    ssh_params = []
    ssh_clients = []
    for host in hosts:
        ssh_params.append(read_ssh_config(host))
    for ssh_param in ssh_params:
        ssh_clients.append(connect_ssh_client(ssh_param))


def close_ssh_clients(ssh_clients: List[paramiko.SSHClient]):
    for client in ssh_clients:
        client.close()


def create_all_ssh_clients(
        config_path=DEFAULT_SSH_CONFIG_PATH) -> List[paramiko.SSHClient]:
    """
        Creates list of SSHClient objects from ssh config file.
        Arg:
            config_path:
                ssh configuration file path.
        Returns:    
            List containing all open ssh_clients.
    """
    hosts = get_host_entries(config_path)
    ssh_params = []
    ssh_clients = []
    for host in hosts:
        ssh_params.append(read_ssh_config(host))
    for ssh_param in ssh_params:
        ssh_clients.append(connect_ssh_client(ssh_param))
    return ssh_clients


def check_reachable(ssh_params: SSHParams):
    """ Sanity check to make sure login node is reachable via SSH.
        Args:
            ssh_params: dataclass which includes necessary information to establish SSH connection.

        Returns: 
            Whether remote host is reachable or not.
    """
    ssh_struct = connect_ssh_client(ssh_params)
    return ssh_struct


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
    # Connect to the SSH server
    reachability_flag = True
    try:
        if ssh_params.uses_passkey:  # Connect with passkey
            ssh_client.connect(hostname=ssh_params.remote_hostname,
                               username=ssh_params.remote_username,
                               password=ssh_params.passkey)
            logging.info('Host: ' + ssh_params.remote_hostname + '@' +
                         ssh_params.remote_username + ' Reachable')
        else:
            if ssh_params.rsa_key == None:  # Connect with autogen private key
                ssh_client.connect(hostname=ssh_params.remote_hostname,
                                   username=ssh_params.remote_username)
            else:  # Connect with specific private key file
                ssh_client.connect(hostname=ssh_params.remote_hostname,
                                   username=ssh_params.remote_username,
                                   pkey=ssh_params.rsa_key)
            logging.info('Host: ' + ssh_params.remote_hostname + '@' +
                         ssh_params.remote_username + ' Reachable')
    except paramiko.AuthenticationException:
        logging.info('Unable to authenticate user, please check configuration')
        reachability_flag = False
    except paramiko.SSHException:
        logging.info('SSH protocol negotiation failed, \
        please check if remote server is reachable')
        reachability_flag = False
    except Exception:
        logging.info("Unexpected exception")
        reachability_flag = False
    if not reachability_flag:
        return SSHStruct(SSHStatusEnum.NOT_REACHABLE, ssh_client)
    return SSHStruct(SSHStatusEnum.REACHABLE, ssh_client)


def create_ssh_client(ssh_params: SSHParams):
    """Connects and returns SSH client object.
        This is assuming you are certain the remote host is reachable.

        Args: 
         ssh_params: dataclass which includes necessary information to establish SSH connection.
        Returns:
            Paramiko SSH client object
    """
    return connect_ssh_client(ssh_params).ssh_client


def verify_ssh_client(ssh_params: SSHParams):
    """ Sanity check to make sure remote host is reachable, and returns the connected SSHClient object.
        Closes the connection afterwards.
        Args:
            ssh_params: struct of information needed to establish an SSH connection.
        Returns:
            List[SSH connection success, paramiko SSHClient object]
    """
    ssh_struct = connect_ssh_client(ssh_params)
    if ssh_struct.status:
        ssh_struct.ssh_client.close()
        return ssh_struct.status
    else:
        return ssh_struct.status


def ssh_send_command(ssh_client: paramiko.SSHClient,
                     command: str,
                     is_async: bool = False) -> Tuple[int, str]:
    """Sends command to remote machine over ssh pipe"""
    _, stdout, _ = ssh_client.exec_command(command)
    if is_async:
        # maybe just log here?
        return None, None
    return stdout.channel.recv_exit_status(), stdout.read().decode().strip()


if __name__ == '__main__':
    print(read_ssh_config('mac'))
    print(get_host_entries())

    # client = create_ssh_client(ssh_params)
    # sftp_client = connect_sftp_client(ssh_params)
    print('done')
    # send_scp_async(sftp_client, file_dict)
