#!/bin/bash

# Download and execute the RKE2 installation script with the agent type specified
curl -sfL https://get.rke2.io | INSTALL_RKE2_TYPE="agent" sh -

# Enable the RKE2 agent service
systemctl enable rke2-agent.service

# Create the configuration directory
mkdir -p /etc/rancher/rke2/

# Create the configuration file with cluster IP and token
echo -e "server: $CLUSTER_IP\ntoken: $RKE2_TOKEN" | tee /etc/rancher/rke2/config.yaml

# Start the RKE2 agent service
systemctl start rke2-agent.service
