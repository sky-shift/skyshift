import paramiko 
import os
import logging
import enum
from skyflow.globals import SKYCONF_DIR
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any
from scp import SCPClient
import time
import threading
from paramiko.config import SSHConfig
from skyflow.utils.ssh_utils import *
from threading import Thread

paramiko.util.log_to_file(os.path.expanduser(PARAMIKO_LOG_PATH))
logging.basicConfig(
    level=logging.INFO,
    format="%(name)s - %(asctime)s - %(levelname)s - %(message)s")

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
def create_all_scp_clients(ssh_clients: List[paramiko.SSHClient]):
    """Creates list of transport clients from list ssh_clients"""
    scp_clients = []
    for client in ssh_clients:
        scp_clients.append(SCPClient(client.get_transport()))
    return scp_clients
def create_scp_client(ssh_client: paramiko.SSHClient):
    """
        Creates connects paramiko transport client object.
        Args:
            ssh_client:
                Existing connected Paramiko ssh client object.
        Returns:
            List[bool of connection status, Connected paramiko transport client]
    """
    return SCPClient(ssh_client.get_transport(), progress=progress)
def create_and_send_scp(file_path_dict: Dict[str, str], ssh_params: SSHParams, is_async=False):
    """"
        Establishes scp connection, and sends all files before closing the connection.
        Args:
            file_path_dict: Local file paths as keys, and destination file paths as values.
            ssh_params: Struct of parameters required to establish a SSH connection.
            is_async: Whether we send files asynchronously, or block and send one by one.
        Returns:
            Whether the connection succeeded.
    """
    ssh_struct = connect_ssh_client(ssh_params)
    #Check if transport client failed to connect to remote host.
    if ssh_struct.status == SSHStatusEnum.NOT_REACHABLE:
        return False
    scp_client = create_scp_client(ssh_struct.ssh_client)
    send_scp_sync(scp_client, file_path_dict)
    scp_client.close()
    return True
def send_scp_sync(scp_client: SCPClient, file_path_dict: Dict[str, str]):
    """
        Synchronous file transfer, waits until files are present on remote before return.
        Args: 
            scp_client: Connected SCP client object.
            file_path_dict: Dict of local file paths and remote file paths.
    """
    file_transfers = convert_file_path_dict_to_struct(file_path_dict, FileDirEnum.SEND)
    start_scp_threads(scp_client, file_transfers)
def get_scp_sync(scp_client: SCPClient, file_path_dict: Dict[str, str]):
    """
        Synchronous file retrieval, waits until files are presents locally before return.
        Args:
            scp: Connected SCP client object.
            file_path_dict: Dict of remote file paths and local file paths.
    """
    file_transfers = convert_file_path_dict_to_struct(file_path_dict, FileDirEnum.RECIEVE)
    start_scp_threads(scp_client, file_transfers)
def wait_until_file_received(sftp, local_file, remote_file):
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
    logging.info("%s's progress: %.2f%%   \r" % (filename, float(sent)/float(size)*100) )
class FileDirEnum(enum.Enum):
    RECEIVE =  'RECEIVE'
    SEND = 'SEND'
@dataclass 
class FileTransferStruct():
    def __init__(self, local_file, remote_file: str, direction: FileDirEnum=FileDirEnum.SEND):
        self.local_file = local_file
        self.remote_file = remote_file
        self.direction = direction


def convert_file_path_dict_to_struct(file_path_dict: Dict[str, str], direction: FileDirEnum) -> List[FileTransferStruct]:
    """
        Converts a dictionary of file paths to a list of file transfer structs.
        Args:
            file_path_dict: Dict of local file paths and remote file paths.
            direction: Enum of whether we are sending or recieving files.
        Returns:
            List of file transfer structs.
    """
    file_structs = []
    for local_file_path in file_path_dict:
        remote_file_path = file_path_dict[local_file_path]
        file_structs.append(FileTransferStruct(local_file_path, remote_file_path, direction))
    return file_structs


class SCPTransferThread(threading.Thread):
    """
        Spawn multiple SCP clients to multithread file transfers.
    """
    def __init__(self, scp_client: SCPClient, file_struct: FileTransferStruct):
        super().__init__()
        self.scp_client = scp_client
        self.file_struct = file_struct

    def run(self):
        if self.file_struct.direction == FileDirEnum.SEND:
            self.scp_client.put(self.file_struct.local_file, self.file_struct.remote_file, preserve_times=True, recursive=False)
        else:
            self.scp_client.get(self.file_struct.remote_file, self.file_struct.local_file, preserve_times=True, recursive=False)
def start_scp_threads(scp_client: SCPClient, ftp_structs:List[FileTransferStruct]):
    threads = []
    for ftp_struct in ftp_structs:
        thread = Thread(target=SCPTransferThread(scp_client, ftp_struct))
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join()
if __name__ == '__main__':
    ssh_params = (read_ssh_config('mac'))
    big_file = '/home/cdaron/projects/skyflow/skyflow/utils/archlinux-2024.05.01-x86_64.iso'
    small_file = '/home/cdaron/projects/skyflow/skyflow/utils/20M.txt'
    send_file_dict = {small_file:'/Users/daronchang/skytest20M.txt'}
    rec_file_dict = {'/Users/daronchang/skytest20M.txt': small_file+'.test'}
    ssh_client = read_and_connect_from_config('mac')
    print(ssh_client)
    scp_client = create_scp_client(ssh_client)
    send_scp_sync(scp_client, send_file_dict)
    get_scp_sync(scp_client, rec_file_dict)
    print('done')
    #send_scp_async(sftp_client, file_dict)