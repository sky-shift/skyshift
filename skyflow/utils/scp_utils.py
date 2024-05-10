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
def create_scp_client(ssh_client):
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
        Synchronous file transfer, waits until file is present on remote before return.
        Args: 
            sftp: Connected paramiko STFPClient object.
            file_path_dict: Dict of local file paths and remote file paths.
    """
    for local_file_path in file_path_dict:
        remote_file_path = file_path_dict[local_file_path]
        scp_client.put(files=local_file_path, remote_path=remote_file_path)
def get_scp_sync(scp: SCPClient, file_path_dict: Dict[str, str]):
    """Sync file transfer, sends files and does not wait.
    """
    for local_file_path in file_path_dict:
        remote_file_path = file_path_dict[local_file_path]
        scp.get(remote_path = remote_file_path, local_path=local_file_path)
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
    logging.info("%s's progress: %.2f%%   \r" % (filename, float(sent)/float(size)*100) )
class FileDirEnum(enum.Enum):
    RECIEVE =  'RECIEVE'
    SEND = 'SEND'
@dataclass 
class FileTransferStruct():
    def __init__(self, local_file, remote_file: str, direction: FileDirEnum=FileDirEnum.SEND):
        self.local_file = local_file
        self.remote_file = remote_file
        self.direction = direction
class SCPTransferThread(threading.Thread):
    """
        Spawn multiple SCP clients to multithread file transfers.
        TODO Async thread spawn and join after done
    """
    def __init__(self, scp_client: SCPClient, file_struct: FileTransferStruct):
        super().__init__()
        self.scp_client = scp_client
        self.file_struct = file_struct

    def run(self):
        if self.file_struct.direction == FileDirEnum.SEND:
            self.scp_client.put(self.local_file, self.remote_file, preserve_times=True, recursive=False)
        else:
            self.scp_client.get(self.remote_file, self.local_file, preserve_times=True, recursive=False)
def start_SCP_threads(ssh_client, ftp_structs:List[FileTransferStruct]):
    threads = []
    for ftp_struct in len(ftp_structs.keys()):
        thread = Thread(target=SCPTransferThread(ssh_client, ftp_struct))
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