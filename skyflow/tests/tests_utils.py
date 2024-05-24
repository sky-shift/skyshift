"""
Common utilities shared by all tests.
"""

import logging
import os
import shutil
import subprocess
import time


def setup_skyflow(temp_data_dir: str) -> None:
    """
    Sets up the Skyflow service by starting the necessary processes.

    Args:
        temp_data_dir (str): The temporary directory to use for data storage.

    Raises:
        RuntimeError: If the server does not start within the expected time frame.
    """
    time.sleep(5)  # Wait for any previous processes to terminate.
    print("Using temporary data directory for ETCD:", temp_data_dir)

    skyconf_dir = os.path.expanduser("~/.skyconf/")
    dest_skyconf_dir = os.path.join(temp_data_dir, ".skyconf")
    if os.path.exists(dest_skyconf_dir):
        # Remove the backup directory if it exists.
        shutil.rmtree(dest_skyconf_dir)

    if os.path.exists(skyconf_dir):
        shutil.copytree(skyconf_dir, dest_skyconf_dir)
        print(f"Copied {skyconf_dir} to {dest_skyconf_dir}.")

    workers = 1  # Number of worker processes to use.
    # Retrieves the absolute path to the launch script.
    install_script_path = retrieve_current_working_dir(
        "../../api_server/launch_server.py")

    # Command to start the server process.
    command = [
        "python", install_script_path, "--workers",
        str(workers), "--data-directory", temp_data_dir
    ]
    # Starts the server process asynchronously.
    subprocess.Popen(command)

    timeout = 60  # Maximum time to wait for the server to start, in seconds.
    start_time = time.time()
    # Polls the process status until both required services are running or timeout.
    while (not is_process_running("launch_server")
           or not is_process_running("etcd")
           ) and time.time() - start_time < timeout:
        time.sleep(1)  # Check the process status every second.

    # Checks if the server failed to start within the timeout period.
    if not is_process_running("launch_server") or not is_process_running(
            "etcd"):
        raise RuntimeError("Server did not start within the expected time.")

    time.sleep(
        20)  # Additional wait time for the server to become fully operational.


def shutdown_skyflow(temporal_directory: str) -> None:
    """
    Shuts down the Skyflow service by terminating its processes.
    """

    kill_process("launch_sky_manager")
    kill_process("launch_server")
    kill_process("etcd")
    # Path to the backed up .skyconf directory within the temporary directory.
    backup_skyconf_dir = os.path.join(temporal_directory, ".skyconf")

    # Original .skyconf directory path.
    original_skyconf_dir = os.path.expanduser("~/.skyconf")

    # Check if the backup exists.
    if os.path.exists(backup_skyconf_dir):
        # Remove the current .skyconf directory if it exists to avoid conflicts.
        if os.path.exists(original_skyconf_dir):
            shutil.rmtree(original_skyconf_dir)
        # Move the backup to the original location.
        shutil.move(backup_skyconf_dir, original_skyconf_dir)
        print(f"Restored {original_skyconf_dir} from the backup.")
    else:
        print(
            f"No backup found in {backup_skyconf_dir}. No action taken for ~/.skyconf restoration."
        )

    if os.path.exists(temporal_directory):
        shutil.rmtree(temporal_directory)
        print(f"Removed temporary directory {temporal_directory}")


def kill_process(process_name: str) -> None:
    """
    Attempts to kill a process by name.

    Args:
        process_name (str): The name of the process to terminate.
    """
    try:
        print("Killing process:", process_name)
        command = f"sudo pkill -9 -f '{process_name}'"
        subprocess.run(command, shell=True, check=True)
        print(f"Successfully killed process {process_name}")
    except subprocess.CalledProcessError:
        print(f"Failed to kill process {process_name}")


def retrieve_current_working_dir(relative_path_to_script: str) -> str:
    """
    Retrieves the absolute path to a script, given its relative path.

    Args:
        relative_path_to_script (str): The relative path from this script to the target.

    Returns:
        str: The absolute path to the target script.
    """
    current_file_path = os.path.abspath(__file__)
    current_directory = os.path.dirname(current_file_path)
    install_script_path = os.path.abspath(
        os.path.join(current_directory, relative_path_to_script))
    return install_script_path


def is_process_running(process_name: str) -> bool:
    """
    Checks if a process with the given name is currently running.

    Args:
        process_name (str): The name of the process to check.

    Returns:
        bool: True if the process is running, False otherwise.
    """
    try:
        # Uses grep to search for the process, avoiding matching the grep command itself.
        command = f"ps aux | grep '[{process_name[0]}]{process_name[1:]}'"
        result = subprocess.run(command,
                                shell=True,
                                check=True,
                                stdout=subprocess.PIPE,
                                text=True)

        # Splits the output by newline to get individual lines.
        output_lines = result.stdout.strip().split('\n')
        # If there's at least one line, the process is running.
        return len(output_lines) >= 1
    except subprocess.CalledProcessError:
        # If an error occurs (e.g., the process is not found), returns False.
        return False


def create_cluster(name: str):
    """
    Creates a KIND Cluster

    Prerequisites :
        KIND (https://kind.sigs.k8s.io)
        DOCKER
        KUBECTL
    """
    logging.debug('Creating cluster %s', name)
    os.system(f"kind create cluster  --name={name}")

    cluster_info_cmd = (f'kubectl cluster-info --context kind-{name}')
    try:
        subprocess.check_output(cluster_info_cmd,
                                shell=True,
                                stderr=subprocess.STDOUT).decode('utf-8')
        return True
    except subprocess.CalledProcessError:
        return False


def delete_cluster(name: str):
    """
    Deletes a KIND Cluster
    """
    logging.debug('Deleting cluster %s', name)
    os.system(f"kind delete cluster --name={name}")
