#!/bin/bash

ETCD_VER=v3.5.11

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

rm -f /tmp/etcd-${ETCD_VER}-linux-amd64.tar.gz
rm -rf /tmp/etcd-download-test && mkdir -p /tmp/etcd-download-test

curl -s -L ${DOWNLOAD_URL}/${ETCD_VER}/etcd-${ETCD_VER}-linux-amd64.tar.gz -o /tmp/etcd-${ETCD_VER}-linux-amd64.tar.gz
tar xzvf /tmp/etcd-${ETCD_VER}-linux-amd64.tar.gz -C /tmp/etcd-download-test --strip-components=1
rm -f /tmp/etcd-${ETCD_VER}-linux-amd64.tar.gz

mkdir -p ${DATA_DIR}

cp /tmp/etcd-download-test/etcd ${DATA_DIR}/
cp /tmp/etcd-download-test/etcdctl ${DATA_DIR}/

nohup ${DATA_DIR}/etcd --data-dir ${DATA_DIR} > /dev/null 2>&1 &
