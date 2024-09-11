Provisioning Kubernetes Clusters on the Sky
========

SkyShift's cloud feature supports the dynamic provisioning of kubernetes cluster on cloud providers. 

SkyPilot + RKE2
---------------
SkyShift uses a combination of SkyPilot and Rancher RKE2 to dynamically provision kubernetes clusters on the cloud. 

Provisioner Controller
----------------------

The Provisioner Controller is responsible for ensuring that the state of the provisioned/provisioning cluster matches the state in etcd. 
We introduce an additional ``provisioning`` state to the cluster object to indicate that the cluster is being provisioned. 

Authentication and KUBECONFIG files are copied back to the host machine. 