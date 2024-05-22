"""
Launches the API server for Sky Manager.
"""
import argparse
import multiprocessing
import os
import subprocess
from typing import Optional
import requests

import uvicorn
from etcd3.exceptions import ConnectionFailedError

from skyflow.etcd_client.etcd_client import ETCDClient
from skyflow.utils.utils import generate_manager_config, generate_temp_directory
from api_server import remove_flag_file
from api_server import CONF_FLAG_DIR
API_SERVER_HOST = "127.0.0.1"
API_SERVER_PORT = 50051


def check_and_install_etcd(data_directory: Optional[str] = None) -> bool:
    """
    Checks if ETCD is installed and running. If not, installs and launches ETCD.
    """
    try:
        ETCDClient().read_prefix("namespaces")
        print("[Installer] ETCD is running.")
        return True
    except ConnectionFailedError:
        print(
            "[Installer] ETCD is not running, automatically installing ETCD.")

    relative_dir = os.path.dirname(os.path.realpath(__file__))
    install_command = f"{relative_dir}/install_etcd.sh"
    # Pass data_directory to the install script if provided
    if data_directory:
        install_command += f" {data_directory}"

    with subprocess.Popen(install_command, shell=True,
                          start_new_session=True) as install_process:
        install_process.wait()  # Wait for the script to complete
        install_rc = install_process.returncode
    if install_rc == 0:
        print("[Installer] Successfully installed and launched ETCD.")
        return True
    print(
        "[Installer] ETCD failed to install and launch. Try manually installing ETCD."
    )
    return False


def check_and_install_minio(data_directory: Optional[str] = None, access_key: str = 'minioadmin', 
                            secret_key: str = 'minioadmin', server_port: str = '9000', console_port: str = '9001') -> bool:
    """
    Checks if MinIO is installed and running. If not, installs and launches MinIO.
    
    Parameters:
    - data_directory: Optional; specifies the data storage directory for MinIO.
    - access_key: MinIO access key, defaults to 'minioadmin'.
    - secret_key: MinIO secret key, defaults to 'minioadmin'.
    - server_port: Port for the MinIO server, defaults to '9000'.
    - console_port: Port for the MinIO management console, defaults to '9001'.
    """
    try:
        # Try to connect to MinIO server
        response = requests.get(f"http://localhost:{server_port}/minio/health/live")
        if response.status_code == 200:
            print("[Installer] MinIO is running.")
            return True
    except requests.exceptions.RequestException:
        print("[Installer] MinIO is not running, automatically installing MinIO.")

    relative_dir = os.path.dirname(os.path.realpath(__file__))
    install_command = f"{relative_dir}/install_minio.sh {data_directory} {access_key} {secret_key} {server_port} {console_port}"

    with subprocess.Popen(install_command, shell=True, start_new_session=True) as install_process:
        install_process.wait()  # Wait for the script to complete
        install_rc = install_process.returncode
    if install_rc == 0:
        print("[Installer] Successfully installed and launched MinIO.")
        return True
    print("[Installer] MinIO failed to install and launch. Try manually installing MinIO.")
    return False


def main(host: str, port: int, workers: int, reset: bool, data_directory=None, ):
    """Main function that encapsulates the script logic, now supports specifying data directory."""
    # Check if etcd is installed and running - elsewise, install and launch etcd.
    if not check_and_install_etcd(data_directory):
        return
    generate_manager_config(host, port)
    #Create temperorary directory used for worker sync
    generate_temp_directory(CONF_FLAG_DIR)
    #Remove flag to trigger new initialzations
    if reset:
        remove_flag_file()
    uvicorn.run(
        "api_server:app",
        host=host,
        port=port,
        workers=workers,
    )


def parse_args():
    """Parse and return command line arguments, now includes data directory."""
    parser = argparse.ArgumentParser(description="Launch API Service.")
    parser.add_argument(
        "--host",
        type=str,
        default=API_SERVER_HOST,
        help="Host for the API server (default: %(default)s)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=API_SERVER_PORT,
        help="Port for the API server (default: %(default)s)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=multiprocessing.cpu_count(),
        help=
        "Number of workers running in parallel for the API server (default: %(default)s)",
    )
    parser.add_argument(
        "--data-directory",
        type=str,
        help="Optional directory for ETCD data (default: uses ~/.etcd/)",
    )
    parser.add_argument(
        "--reset",
        action='store_true',
        help="Rewrite configuration file (default: False)",
    )
    return parser.parse_args()


# Faster way to run API server:
# `gunicorn --log-level error -w 4 -k uvicorn.workers.UvicornWorker
# -b :50051 api_server.api_server:app`
if __name__ == "__main__":
    args = parse_args()
    main(host=args.host, port=args.port, workers=args.workers, 
         data_directory=args.data_directory, reset=args.reset)
