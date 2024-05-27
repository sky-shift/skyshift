"""
Module for handling SCP file transfers using paramiko and scp libraries.
"""

import enum
import logging
import os
import time
from dataclasses import dataclass
from threading import Thread
from typing import Dict, List, Optional

import paramiko
from scp import SCPClient  # pylint: disable=import-error

from skyflow.utils.ssh_utils import (SSHParams, SSHStatusEnum,
                                     connect_ssh_client)

logging.basicConfig(
    level=logging.INFO,
    format="%(name)s - %(asctime)s - %(levelname)s - %(message)s")


def create_scp_client(ssh_client: paramiko.SSHClient) -> SCPClient:
    """
    Creates and opens SCP client.
    Args:
        ssh_client: A Paramiko opened SSH client object.
    Returns:
        SCP client object
    """
    return SCPClient(ssh_client.get_transport())


def create_all_scp_clients(
        ssh_clients: List[paramiko.SSHClient]) -> List[SCPClient]:
    """
    Creates a list of SCP clients from a list of SSH clients.
    Args:
        ssh_clients: List of paramiko SSHClient objects.
    Returns:
        List of SCPClient objects.
    """
    return [SCPClient(client.get_transport()) for client in ssh_clients]


def create_and_send_scp(file_path_dict: Dict[str, str],
                        ssh_parameters: SSHParams) -> bool:
    """
    Establishes SCP connection and sends all files before closing the connection.
    Args:
        file_path_dict: Local file paths as keys, and destination file paths as values.
        ssh_parameters: Struct of parameters required to establish a SSH connection.
    Returns:
        Whether the connection succeeded.
    """
    ssh_struct = connect_ssh_client(ssh_parameters)
    if ssh_struct.status == SSHStatusEnum.NOT_REACHABLE:
        return False
    if ssh_struct.ssh_client is None:
        raise ValueError("SSH client is None")
    scp_client_instance = create_scp_client(ssh_struct.ssh_client)
    send_scp_sync(scp_client_instance, file_path_dict)
    scp_client_instance.close()
    return True


def send_scp_sync(scp_client_instance: SCPClient, file_path_dict: Dict[str,
                                                                       str]):
    """
    Synchronous file transfer, waits until file is present on remote before returning.
    Args:
        scp_client_instance: Connected paramiko SCPClient object.
        file_path_dict: Dict of local file paths and remote file paths.
    """
    for local_file_path, remote_file_path in file_path_dict.items():
        scp_client_instance.put(files=local_file_path,
                                remote_path=remote_file_path)


def get_scp_sync(scp_client_instance: SCPClient, file_path_dict: Dict[str,
                                                                      str]):
    """
    Synchronous file transfer, retrieves files from remote.
    Args:
        scp_client_instance: Connected paramiko SCPClient object.
        file_path_dict: Dict of remote file paths and local file paths.
    """
    for local_file_path, remote_file_path in file_path_dict.items():
        scp_client_instance.get(remote_path=remote_file_path,
                                local_path=local_file_path)


def wait_until_file_received(sftp: Optional[paramiko.SFTPClient],
                             local_file: str, remote_file: str):
    """
    Waits until the file is received.
    Args:
        sftp: Optional paramiko SFTPClient object.
        local_file: Local file path.
        remote_file: Remote file path.
    """
    if not sftp:
        raise ValueError("SFTP client is None")
    while True:
        try:
            remote_file_size = sftp.stat(remote_file).st_size
            local_file_size = os.path.getsize(local_file)
            if remote_file_size == local_file_size:
                return
        except FileNotFoundError:
            pass
        time.sleep(2)


def wait_until_file_sent(transport: paramiko.Transport, remote_file: str):
    """
    Waits until the file is sent.
    Args:
        transport: Paramiko Transport object.
        remote_file: Remote file path.
    """
    sftp = paramiko.SFTPClient.from_transport(transport)
    if not sftp:
        raise ValueError("SFTP client is None")
    prev_size = 0
    while True:
        try:
            file_attr = sftp.stat(remote_file)
            if not file_attr.st_size:
                continue
            curr_size = file_attr.st_size
            if curr_size == prev_size:
                break  # File transfer completed
            prev_size = curr_size
        except FileNotFoundError:
            pass
        time.sleep(2)


def progress(filename: str, size: int, sent: int):
    """
    Logs the progress of file transfer.
    Args:
        filename: Name of the file being transferred.
        size: Total size of the file.
        sent: Amount of data sent.
    """
    logging.info("%s's progress: %.2f%%   \r", filename,
                 float(sent) / float(size) * 100)


class FileDirEnum(enum.Enum):
    """File transfer direction."""
    RECEIVE = 'RECEIVE'
    SEND = 'SEND'


@dataclass
class FileTransferStruct:
    """Dataclass for file transfer."""
    local_file: str
    remote_file: str
    direction: FileDirEnum = FileDirEnum.SEND


class SCPTransferThread(Thread):
    """
    Spawn multiple SCP clients to multithread file transfers.
    TODO: Async thread spawn and join after done
    """

    def __init__(self, scp_client_instance: SCPClient,
                 file_struct: FileTransferStruct):
        super().__init__()
        self.scp_client_instance = scp_client_instance
        self.file_struct = file_struct

    def run(self):
        if self.file_struct.direction == FileDirEnum.SEND:
            self.scp_client_instance.put(self.file_struct.local_file,
                                         self.file_struct.remote_file,
                                         preserve_times=True,
                                         recursive=False)
        else:
            self.scp_client_instance.get(self.file_struct.remote_file,
                                         self.file_struct.local_file,
                                         preserve_times=True,
                                         recursive=False)


def start_scp_threads(ssh_client_instance: paramiko.SSHClient,
                      ftp_structs: List[FileTransferStruct]):
    """
    Starts multiple SCP transfer threads.
    Args:
        ssh_client_instance: Paramiko SSHClient object.
        ftp_structs: List of FileTransferStruct objects.
    """
    threads = []
    for ftp_struct in ftp_structs:
        thread = SCPTransferThread(
            SCPClient(ssh_client_instance.get_transport()), ftp_struct)
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join()


#if __name__ == '__main__':
#    ssh_parameters = read_ssh_config('mac')
#    BIG_FILE = '/home/cdaron/projects/skyflow/skyflow/utils/archlinux-2024.05.01-x86_64.iso'
#    SMALL_FILE = '/home/cdaron/projects/skyflow/skyflow/utils/20M.txt'
#    send_file_dict = {SMALL_FILE: '/Users/daronchang/skytest20M.txt'}
#    rec_file_dict = {'/Users/daronchang/skytest20M.txt': SMALL_FILE + '.test'}
#    ssh_client_instance = read_and_connect_from_config('mac')
#    print(ssh_client_instance)
#    scp = create_scp_client(ssh_client_instance)
#    send_scp_sync(scp, send_file_dict)
#    get_scp_sync(scp_client_instance, rec_file_dict)
#    print('done')
#    # send_scp_async(sftp_client, file_dict)