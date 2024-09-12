Provisioning Kubernetes Clusters on the Sky
========

SkyShift's cloud feature supports the dynamic provisioning of kubernetes cluster on cloud providers. 
It uses a combination of SkyPilot and Rancher RKE2 to dynamically provision kubernetes clusters across the cheapest VMs on the sky. 

Setup
-----

Ensure that you have correctly set up access to the relevant clouds by following these `instructions <https://skypilot.readthedocs.io/en/latest/getting-started/installation.html#verifying-cloud-access>`_ from the SkyPilot documentation. 

SkyPilot + RKE2
---------------

Individual VMs are provisioned using SkyPilot, and they are interfaced together into a kubernetes cluster using RKE2. 
For each cloud provisioned cluster, the first VM is the dedicated server node and each subsequent VM is a worker node. 
The RKE2 token and KUBECONFIG files are copied back to the host machine to be used by the worker nodes for authentication purposes. 
Each provisioned node is contains the same specs, which are specified on cluster creation. 
Additionally, the `NVIDIA Device Plugin <https://github.com/NVIDIA/k8s-device-plugin>`_ and `NVIDIA GPU Operator <https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/index.html>`_ are installed on every node to enable GPU support.  

Provisioner Controller
----------------------

The Provisioner Controller is responsible for ensuring that the state of the provisioned/provisioning cluster matches the state in etcd. 
We introduce an additional ``provisioning`` state to the cluster object to indicate that the cluster is being provisioned. 

Utilizing the Cluster
---------------------

The KUBECONFIG for the provisioned cluster is stored at ``~/.skyconf/clusters/{cluster_name}/kubeconfig``. 
To use the ``kubectl`` CLI with the provisioned cluster, you can set the KUBECONFIG environment variable to this path. 
