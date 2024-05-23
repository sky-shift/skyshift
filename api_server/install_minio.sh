#!/bin/bash
# MinIO Installation Script
#
# This script downloads and installs MinIO.
#
# Usage:
#    bash install_minio.sh [data_dir] [admin_username] [admin_password] [server_port] [console_port]
#
# Options:
#    data_dir:    Specify a custom directory for MinIO data storage. 
#    admin_username:  Specify the MinIO access key. 
#    admin_password:  Specify the MinIO secret key. 
#    server_host: Specify the address for the MinIO server.
#    server_port: Specify the port for the MinIO server. 
#    console_port: Specify the port for the MinIO console. 
#
# This script supports downloading MinIO from the official site.
# It cleans up the downloaded binaries after installation is complete.
# Ensure you have wget or curl installed and accessible in your PATH to successfully run this script.

set -e

DATA_DIR=${1}
ADMIN_USERNAME=${2}
ADMIN_PASSWORD=${3}
SERVER_HOST=${4}
SERVER_PORT=${5}
CONSOLE_PORT=${6}

# Define valid platforms
VALID_PLATFORMS=("linux" "darwin" "windows")
# Automatically identify the platform and architecture (lower case)
UNAME=$(uname | tr "[:upper:]" "[:lower:]")
# Check if the platform is valid
if [[ ! " ${VALID_PLATFORMS[@]} " =~ " ${UNAME} " ]]; then
  echo "Unsupported platform: ${UNAME}"
  echo "Supported platforms: ${VALID_PLATFORMS[@]}"
  exit 1
fi

FILE_ENDING="tar.gz"
# if linux, set to tar.gz
if [[ $UNAME == "linux" ]]; then
  FILE_ENDING="tar.gz"
fi

# if darwin or windows set to zip
if [[ $UNAME == "darwin" || $UNAME == "windows" ]]; then
  FILE_ENDING="zip"
fi

# Define valid architectures
VALID_ARCHS=("amd64" "arm64" "ppc64le" "s390x")
# Identify architecture [amd64, arm64, ppc64le, s390x]
ARCH=$(uname -m)
# if arch is in [x86, x86_64, x64], set to amd64.
if [[ $ARCH == "x86_64" || $ARCH == "x64" || $ARCH == "x86" ]]; then
  ARCH="amd64"
fi
# if arch is in [aarch64, armv8, armv8l], set to arm64.
if [[ $ARCH == "aarch64" || $ARCH == "armv8" || $ARCH == "armv8l" ]]; then
  ARCH="arm64"
fi

# Check if the architecture is valid
if [[ ! " ${VALID_ARCHS[@]} " =~ " ${ARCH} " ]]; then
  echo "Unsupported architecture: ${ARCH}"
  echo "Supported architectures: ${VALID_ARCHS[@]}"
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

# Set environment variables
export MINIO_ROOT_USER="${ADMIN_USERNAME}"
export MINIO_ROOT_PASSWORD="${ADMIN_PASSWORD}"

# Run MinIO
echo "Starting MinIO on ports ${SERVER_PORT} for server and ${CONSOLE_PORT} for console..."
nohup ./minio server ${DATA_DIR} --address ${SERVER_HOST}:${SERVER_PORT} --console-address ${SERVER_HOST}:${CONSOLE_PORT} \
    > minio.log 2>&1 &

echo "MinIO is running with data directory at ${DATA_DIR}"
echo "Access it via: ${SERVER_HOST}:${SERVER_PORT}"
echo "Access Console via: ${SERVER_HOST}:${CONSOLE_PORT}"
echo "Access Key: ${ADMIN_USERNAME}, Secret Key: ${ADMIN_PASSWORD}"