"""
Launches the API server for Sky Manager.
"""
import argparse
import multiprocessing
import os
import subprocess

import uvicorn
import yaml

API_SERVER_CONFIG_PATH = "~/.skyconf/config.yaml"
API_SERVER_HOST = "localhost"
API_SERVER_PORT = 50051


def generate_manager_config(host: str, port: int):
    """Generates the API server config file."""
    config_dict = {
        "api_server": {
            "host": host,
            "port": port,
        },
    }
    absolute_path = os.path.expanduser(API_SERVER_CONFIG_PATH)
    os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
    with open(absolute_path, "w") as config_file:
        yaml.dump(config_dict, config_file)


def check_and_install_etcd():
    """Checks if ETCD is installed and running. If not, installs and launches ETCD."""
    result = subprocess.run(
        'ps aux | grep "etcd"',
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    return_code = result.returncode
    if return_code == 0:
        print("[Installer] ETCD is running.")
    else:
        print(
            "[Installer] ETCD is not running, automatically installing ETCD.")
        # Install ETCD (platform-specific code goes here)
        # Start ETCD in background (platform-specific code goes here)
        relative_dir = os.path.dirname(os.path.realpath(__file__))
        with subprocess.Popen(f"{relative_dir}/install_etcd.sh",
                              shell=True,
                              start_new_session=True) as install_process:
            install_process.wait()  # Wait for the script to complete
            install_rc = install_process.returncode
        if install_rc == 0:
            print("[Installer] Successfully installed and launched ETCD.")
        else:
            print(
                "[Installer] ETCD failed to install and launch. Try manually installing ETCD."
            )


# Faster way to run API server:
# `gunicorn --log-level error -w 4 -k uvicorn.workers.UvicornWorker
# -b :50051 api_server.api_server:app`
if __name__ == "__main__":
    # Create the parser
    parser = argparse.ArgumentParser(
        description="Launch API Service for Sky Manager.")

    # Add arguments
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
    # Parse the arguments
    args = parser.parse_args()

    # Check if etcd is installed and running - elsewise, install and launch etcd.
    check_and_install_etcd()
    generate_manager_config(args.host, args.port)
    uvicorn.run(
        "api_server:app",
        host=args.host,
        port=args.port,
        workers=multiprocessing.cpu_count(),
    )
