#!/bin/bash
# ETCD Installation Script
#
# This script downloads and installs ETCD version v3.5.11.
#
# Usage:
#    # To install ETCD with the default data directory.
#    bash install_etcd.sh
#    # To install ETCD with a custom data directory.
#    bash install_etcd.sh <data_dir>
#
# Options:
#    --data_dir: Specify a custom directory for ETCD data storage. If not provided, defaults to ~/.etcd.
#
# This script supports downloading ETCD from either Google Cloud Storage or GitHub Releases, defaulting to Google Cloud Storage.
# It cleans up the downloaded archive and temporary files after installation.
# Run this script to install or update ETCD to the specified version on your system.
#
# Ensure you have curl and tar installed and accessible in your PATH to successfully run this script.

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

ETCD_VER=v3.5.12

# Choose either URL
GOOGLE_URL=https://storage.googleapis.com/etcd
GITHUB_URL=https://github.com/etcd-io/etcd/releases/download
DOWNLOAD_URL=${GOOGLE_URL}

# Check if an argument is passed for data_dir, otherwise use default
if [ "$#" -eq 1 ]; then
  DATA_DIR=$1
else
  DATA_DIR=~/.etcd
fi

echo "Using data directory: ${DATA_DIR}"

rm -f /tmp/etcd-${ETCD_VER}-${UNAME}-${ARCH}.${FILE_ENDING}
rm -rf /tmp/etcd-download-test && mkdir -p /tmp/etcd-download-test

curl -s -L ${DOWNLOAD_URL}/${ETCD_VER}/etcd-${ETCD_VER}-${UNAME}-${ARCH}.${FILE_ENDING} -o /tmp/etcd-${ETCD_VER}-${UNAME}-${ARCH}.${FILE_ENDING}

tar xzvf /tmp/etcd-${ETCD_VER}-${UNAME}-${ARCH}.${FILE_ENDING} -C /tmp/etcd-download-test --strip-components=1
rm -f /tmp/etcd-${ETCD_VER}-${UNAME}-${ARCH}.${FILE_ENDING}

mkdir -p ${DATA_DIR}

cp /tmp/etcd-download-test/etcd ${DATA_DIR}/
cp /tmp/etcd-download-test/etcdctl ${DATA_DIR}/

nohup ${DATA_DIR}/etcd --data-dir ${DATA_DIR} > /dev/null 2>&1 &