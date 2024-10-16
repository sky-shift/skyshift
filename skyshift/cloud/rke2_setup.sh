#!/bin/bash

echo "PUBLIC_IP=$PUBLIC_IP"
echo "CLUSTER_NAME=$CLUSTER_NAME"

# Set KUBECONFIG environment variable
export KUBECONFIG=/etc/rancher/rke2/rke2.yaml

# Install RKE2 using its installation script
curl -sfL https://get.rke2.io | sh -

# Add the RKE2 server configuration file /etc/rancher/rke2/config.yaml to set tls-san using $PUBLIC_IP
mkdir -p /etc/rancher/rke2
echo "
cluster-name: $CLUSTER_NAME
tls-san:
  - $PUBLIC_IP" > /etc/rancher/rke2/config.yaml

# Enable and start the RKE2 server service
systemctl enable rke2-server.service
systemctl start rke2-server.service

# Download and install Helm
curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3
chmod 700 get_helm.sh
./get_helm.sh

# Set the permissions for the KUBECONFIG file
chmod 644 $KUBECONFIG

# Change all instances of 127.0.0.1 to $PUBLIC_IP in KUBECONFIG
sed -i "s/127.0.0.1/$PUBLIC_IP/g" $KUBECONFIG

# Rename the context in KUBECONFIG
kubectl config rename-context default $CLUSTER_NAME --kubeconfig=$KUBECONFIG
kubectl config use-context $CLUSTER_NAME --kubeconfig=$KUBECONFIG

# Create a Kubernetes resource from a remote file
kubectl create -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.14.5/nvidia-device-plugin.yml

# Add the NVIDIA Helm repository and update it
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia
helm repo update

# Install the GPU Operator from the NVIDIA Helm repository
helm install --wait --generate-name -n gpu-operator --create-namespace nvidia/gpu-operator

# Set the permissions for the RKE2 server's data directory
chmod -R 755 /var/lib/rancher
