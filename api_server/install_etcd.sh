# @TODO(mluo,alex): Extend beyond Linux script to support other OS.
ETCD_VER=v3.5.11

# choose either URL
GOOGLE_URL=https://storage.googleapis.com/etcd
GITHUB_URL=https://github.com/etcd-io/etcd/releases/download
DOWNLOAD_URL=${GOOGLE_URL}

rm -f /tmp/etcd-${ETCD_VER}-linux-amd64.tar.gz
rm -rf /tmp/etcd-download-test && mkdir -p /tmp/etcd-download-test

curl -L ${DOWNLOAD_URL}/${ETCD_VER}/etcd-${ETCD_VER}-linux-amd64.tar.gz -o /tmp/etcd-${ETCD_VER}-linux-amd64.tar.gz
tar xzvf /tmp/etcd-${ETCD_VER}-linux-amd64.tar.gz -C /tmp/etcd-download-test --strip-components=1
rm -f /tmp/etcd-${ETCD_VER}-linux-amd64.tar.gz

mkdir -p ~/.etcd

cp /tmp/etcd-download-test/etcd ~/.etcd/
cp /tmp/etcd-download-test/etcdctl ~/.etcd/

nohup ~/.etcd/etcd --data-dir ~/.etcd > /dev/null 2>&1 &
