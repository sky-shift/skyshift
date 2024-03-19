
import os
import subprocess
import time


def setup_skyflow(temp_data_dir: str):
    time.sleep(5)  # Wait for the processes to terminate
    print("Using temporary data directory for ETCD:", temp_data_dir)
    workers = 1
    install_script_path = retrieve_current_working_dir("../../api_server/launch_server.py")
    command = [
        "python", install_script_path, "--workers",
        str(workers), "--data-directory", temp_data_dir
    ]
    subprocess.Popen(command)
    timeout = 60  # Maximum time to wait in seconds
    start_time = time.time()
    while (not is_process_running("launch_server") or not is_process_running("etcd")) and time.time() - start_time < timeout:
        time.sleep(1)  # Check every second
    if not is_process_running("launch_server") or not is_process_running("etcd"):
        raise RuntimeError("Server did not start within the expected time.")
    time.sleep(20)  # Wait for the server to start

def shutdown_skyflow():
    kill_process("launch_sky_manager")
    kill_process("launch_server")
    kill_process("etcd")

def kill_process(process_name):
    try:
        command = f"pkill -f '{process_name}'"
        subprocess.run(command, shell=True, check=True)
    except subprocess.CalledProcessError:
        print(f"Failed to kill process {process_name}")

def retrieve_current_working_dir(relative_path_to_script: str) -> str:
        current_file_path = os.path.abspath(__file__)
        current_directory = os.path.dirname(current_file_path)
        install_script_path = os.path.abspath(
            os.path.join(current_directory, relative_path_to_script))
        return install_script_path

def is_process_running(process_name):
    try:
        command = f"ps aux | grep '[{process_name[0]}]{process_name[1:]}'"
        result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, text=True)

        # Count the number of lines in the output
        output_lines = result.stdout.strip().split('\n')
        return len(output_lines) >= 1
    except subprocess.CalledProcessError:
        return False