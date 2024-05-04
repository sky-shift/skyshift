import paramiko 
import os
import yaml
import logging
import enum
from skyflow.globals import SKYCONF_DIR
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict
from scp import SCPClient
import time
import sys
import threading
from paramiko.config import SSHConfig
DEFAULT_SSH_CONFIG_PATH = '~/.ssh/config'
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
    def __init__(self, remote_hostname=None, remote_username=None,
        rsa_key=None, passkey = None, uses_passkey=False, port=22):
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
class SCPStruct():
    """SCP Client struct for status and scp client"""
    status: SSHStatusEnum
    scp_client: SCPClient
    def __init__(self, status=SSHStatusEnum.NOT_REACHABLE, scp_client=None):
        self.status = status
        self.scp_client = scp_client
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
    absolute_path = os.path.expanduser(config_path)
    config = SSHConfig.from_path(absolute_path)
    host_config = config.lookup(host_entry)
    required_keys = ['hostname', 'user']
    if all(elem in host_config.keys() for elem in required_keys): 
      ssh_params = SSHParams(remote_hostname=host_config['hostname'], 
        remote_username=host_config['user'])
    else:
        return SSHParams()
    return ssh_params
def get_host_entrys(config_path=DEFAULT_SSH_CONFIG_PATH)-> List[str]:
    """
        Returns all hosts configured in SSH config file
        Return:
            List of host entries in ssh configuration file.
    """
    absolute_path = os.path.expanduser(config_path) 
    # Load SSH config file
    config = SSHConfig()
    with open(absolute_path) as f:
        config.parse(f)
    return(config.get_hostnames())
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
        if ssh_params.uses_passkey: #Connect with passkey
            ssh_client.connect(hostname = ssh_params.remote_hostname,
                username = ssh_params.remote_username, password=ssh_params.passkey)
            logging.info('Host: ' + ssh_params.remote_hostname + '@' + ssh_params.remote_username + ' Reachable')
        else:
            if ssh_params.rsa_key == None: #Connect with autogen private key
                ssh_client.connect(hostname = ssh_params.remote_hostname,
                    username = ssh_params.remote_username)
            else: #Connect with specific private key file
                ssh_client.connect(hostname = ssh_params.remote_hostname, 
                    username = ssh_params.remote_username, pkey = ssh_params.rsa_key)
            logging.info('Host: ' + ssh_params.remote_hostname + '@' + ssh_params.remote_username + ' Reachable')
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
def create_scp_client(ssh_client: paramiko.SSHClient) -> SCPClient:
    """
        Creates and opens scp client.
        Args:
            ssh_client:
                A Paramiko opened ssh client object.
        Returns:
            scp client object
    """
    scp = SCPClient(ssh_client.get_transport())
    return scp
def simple_scp(ssh_params, file_path_dict):
    ssh = paramiko.SSHClient()
    #ssh.load_system_host_keys()
    ssh_struct = connect_ssh_client(ssh_params)
    scp = SCPClient(ssh_struct.ssh_client.get_transport())
    for local_file_path in file_path_dict:
        remote_file_path = file_path_dict[local_file_path]
        scp.put(local_file_path, remote_file_path)
def connect_scp_client(ssh_params: SSHParams):
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_struct = connect_ssh_client(ssh_params)
    scp = SCPClient(ssh_struct.ssh_client.get_transport(), progress=progress)
    return SCPStruct(ssh_struct.status, scp)
def create_scp_client(ssh_params: SSHParams):
    """
        Creates connects paramiko transport client object.
        Args:
            ssh_params:
                Struct of parameters required to establish a SSH connection
        Returns:
            List[bool of connection status, Connected paramiko transport client]
    """
    return connect_scp_client(ssh_params).scp_client
def create_and_send_scp(file_path_dict: Dict[str, str], ssh_params: SSHParams, is_async=True):
    """"
        Establishes SFTP connection, and sends all files before closing the connection.
        Args:
            file_path_dict: Local file paths as keys, and destination file paths as values.
            ssh_params: Struct of parameters required to establish a SSH connection.
            is_async: Whether we send files asynchronously, or block and send one by one.
    """
    scp_struct = connect_scp_client(ssh_params)
    #Check if transport client failed to connect to remote host.
    if scp_struct.status == SSHStatusEnum.NOT_REACHABLE:
        return False
    scp_client = scp_struct.scp_client
    if is_async:
        send_scp_async(scp_client, file_path_dict)
    else:
        send_scp_sync(scp_client, file_path_dict)
    scp_client.close()
def send_scp_sync(scp_client: SCPClient, file_path_dict):
    """
        Synchronous file transfer, waits until file is present on remote before return.
        Do we want to spawn asynchronous tasks for this?
        Args: 
            sftp: Connected paramiko STFPClient object.
            file_path_dict: Dict of local file paths and remote file paths.
    """
    for local_file_path in file_path_dict:
        remote_file_path = file_path_dict[local_file_path]
        scp_client.put(local_file_path, remote_file_path)
        wait_until_file_sent(scp_client, remote_file_path)
def send_scp_async(scp_client, file_path_dict):
    """Async file transfer, sends files and does not wait.
    """
    for local_file_path in file_path_dict:
        remote_file_path = file_path_dict[local_file_path]
        scp_client.put(local_file_path, remote_file_path)
def get_scp_sync(sftp: paramiko.SFTPClient, file_path_dict):
    """Async file transfer, sends files and does not wait.
    """
    for local_file_path in file_path_dict:
        remote_file_path = file_path_dict[local_file_path]
        sftp.get(local_file_path, remote_file_path)
def get_scp_async(sftp: paramiko.SFTPClient, file_path_dict):
    """Async file transfer, sends files and does not wait.
    """
    for local_file_path in file_path_dict:
        remote_file_path = file_path_dict[local_file_path]
        sftp.put(local_file_path, remote_file_path)
        wait_until_file_recieved(sftp, remote_file_path)
def wait_until_file_recieved(sftp, local_file, remote_file):
    while True:
        try:
            remote_file_size = sftp.stat(remote_file).st_size
            local_file_size = os.path.getsize(local_file)
            if remote_file_size == local_file_size:
                return
        except FileNotFoundError:
            pass
        time.sleep(2)
def wait_until_file_sent(transport, remote_file):
    sftp = paramiko.SFTPClient.from_transport(transport)
    prev_size = 0
    while True:
        try:
            file_attr = sftp.stat(remote_file)
            curr_size = file_attr.st_size
            if curr_size == prev_size:
                break  # File transfer completed
            prev_size = curr_size
        except FileNotFoundError:
            pass
        time.sleep(2)  
def progress(filename, size, sent):
    sys.stdout.write("%s's progress: %.2f%%   \r" % (filename, float(sent)/float(size)*100) )

class MaintainedSSHConnection():
    def __init__(self, ssh_params):
        self.ssh_params = None
        self.ssh_client = None
        self.tp_client = None
class SCPTransferThread(threading.Thread):
    def __init__(self, scp_client, local_file, remote_file):
        super().__init__()
        self.scp_client = scp_client
        self.local_file = local_file
        self.remote_file = remote_file

    def run(self):
        self.scp.put(self.local_file, self.remote_file, preserve_times=True, recursive=False)

if __name__ == '__main__':
    ssh_params = (read_ssh_config('mac'))
    #client = create_ssh_client(ssh_params)
    #sftp_client = connect_sftp_client(ssh_params)
    big_file = '/home/cdaron/projects/skyflow/skyflow/utils/archlinux-2024.05.01-x86_64.iso'
    file_dict = {big_file:'/Users/daronchang/archlin.iso'}
    scp_client = create_scp_client(ssh_params)
    send_scp_async(scp_client, file_dict)
    print('done')
    #send_scp_async(sftp_client, file_dict)