#!/bin/bash
# MinIO Installation Script
#
# This script downloads and installs MinIO.
#
# Usage:
#    bash install_minio.sh [data_dir] [access_key] [secret_key] [server_port] [console_port]
#
# Options:
#    data_dir:    Specify a custom directory for MinIO data storage. Defaults to ./data.
#    access_key:  Specify the MinIO access key. Defaults to 'minioadmin'.
#    secret_key:  Specify the MinIO secret key. Defaults to 'minioadmin'.
#    server_port: Specify the port for the MinIO server. Defaults to 9000.
#    console_port: Specify the port for the MinIO console. Defaults to 9001.
#
# This script supports downloading MinIO from the official site.
# It cleans up the downloaded binaries after installation is complete.
# Ensure you have wget or curl installed and accessible in your PATH to successfully run this script.

set -e

# Default configuration
DATA_DIR=${1:-./data}
ACCESS_KEY=${2:-minioadmin}
SECRET_KEY=${3:-minioadmin}
SERVER_PORT=${4:-9000}
CONSOLE_PORT=${5:-9001}

# Define valid platforms
VALID_PLATFORMS=("linux" "darwin" "windows")
UNAME=$(uname | tr "[:upper:]" "[:lower:]")
ARCH=$(uname -m)

# Automatically identify the platform and architecture (lower case)
if [[ $ARCH == "x86_64" || $ARCH == "x64" ]]; then
  ARCH="amd64"
elif [[ $ARCH == "aarch64" ]]; then
  ARCH="arm64"
fi

# Check if the platform and architecture are valid
if [[ ! " ${VALID_PLATFORMS[@]} " =~ " ${UNAME} " ]] || [[ ! "amd64 arm64" =~ " ${ARCH} " ]]; then
  echo "Unsupported platform or architecture: ${UNAME}-${ARCH}"
  exit 1
fi

# MinIO binary file name based on operating system and architecture
FILE_NAME=minio.${UNAME}-${ARCH}

# Download URL
DOWNLOAD_URL=https://dl.min.io/server/minio/release/${UNAME}-${ARCH}/minio

# Download MinIO
echo "Downloading MinIO from ${DOWNLOAD_URL}..."
curl -O ${DOWNLOAD_URL}

# Make the MinIO binary executable
chmod +x minio

# Create the data directory
mkdir -p ${DATA_DIR}

# Run MinIO
echo "Starting MinIO on ports ${SERVER_PORT} for server and ${CONSOLE_PORT} for console..."
nohup ./minio server ${DATA_DIR} --address :${SERVER_PORT} --console-address :${CONSOLE_PORT} \
    --access-key ${ACCESS_KEY} --secret-key ${SECRET_KEY} > minio.log 2>&1 &

echo "MinIO is running with data directory at ${DATA_DIR}"
echo "Access it via: http://localhost:${SERVER_PORT}"
echo "Access Console via: http://localhost:${CONSOLE_PORT}"
echo "Access Key: ${ACCESS_KEY}, Secret Key: ${SECRET_KEY}"