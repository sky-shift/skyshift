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

from api_server import CONF_FLAG_DIR, remove_flag_file
from skyflow.etcd_client.etcd_client import ETCDClient
from skyflow.utils.utils import (generate_manager_config,
                                 generate_temp_directory)

API_SERVER_HOST = "0.0.0.0"
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


def main(
    host: str,
    port: int,
    workers: int,
    reset: bool,
    data_directory=None,
):
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
    main(host=args.host,
         port=args.port,
         workers=args.workers,
         data_directory=args.data_directory,
         reset=args.reset)
