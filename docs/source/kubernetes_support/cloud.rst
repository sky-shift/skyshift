Provisioning Kubernetes Clusters on the Sky
========

SkyShift's cloud feature supports the dynamic provisioning of kubernetes cluster on cloud providers. 
It uses a combination of `SkyPilot <https://github.com/skypilot-org/skypilot>`_ and `Rancher RKE2 <https://github.com/rancher/rke2>`_ to dynamically provision kubernetes clusters across the cheapest VMs on the sky. 

Usage
-----

Ensure that access to the relevant clouds are correctly set up by following these `instructions <https://skypilot.readthedocs.io/en/latest/getting-started/installation.html#verifying-cloud-access>`_ from the SkyPilot documentation. 

To provision a cluster, run the create cluster CLI command with the ``--provision`` flag. 

.. code-block:: bash

    $ skyctl create cluster cloud-cluster --provision --cloud gcp --cpus 3+

    ⠴ Creating cluster
    Created cluster cloud-cluster.
    ✔ Creating cluster completed successfully.

Track the progress of provisioning clusters using the get cluster CLI command. 

.. code-block:: bash

    # ======== While provisioning ========
    $ skyctl get clusters

    ⠙ Fetching clusters
    NAME           MANAGER    LABELS    RESOURCES    STATUS        AGE
    cloud-cluster  k8                   {}           PROVISIONING  10s
    ✔ Fetching clusters completed successfully.

    # ======== On completion ========
    $ skyctl get clusters

    ⠙ Fetching clusters
    NAME           MANAGER    LABELS    RESOURCES                  STATUS    AGE
    cloud-cluster  k8                   cpus: 2.01/4.0             READY     4m
                                        memory: 12.67 GB/15.63 GB
                                        disk: 239.15 GB/239.15 GB
    ✔ Fetching clusters completed successfully.

SkyPilot + RKE2
---------------

Individual VMs are provisioned using SkyPilot, and they are interfaced together into a kubernetes cluster using RKE2. 
For each cloud provisioned cluster, the first VM is the dedicated server node and each subsequent VM is a worker node. 
The RKE2 token and KUBECONFIG files are copied back to the host machine to be used by the worker nodes for authentication purposes. 
Each provisioned node has the same specs, which are specified on cluster creation. 
Additionally, the `NVIDIA Device Plugin <https://github.com/NVIDIA/k8s-device-plugin>`_ and `NVIDIA GPU Operator <https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/index.html>`_ are installed on every node to enable native GPU support.  

Provisioner Controller
----------------------

The Provisioner Controller is responsible for ensuring that the state of the provisioned/provisioning cluster matches the state in etcd. 
An additional ``PROVISIONING`` state is introduced to the cluster object to indicate that the cluster is being provisioned. 

Utilizing the Cluster
---------------------

The KUBECONFIG for the provisioned cluster is stored at ``~/.skyconf/clusters/{cluster_name}/kubeconfig``. 
To use the ``kubectl`` CLI with the provisioned cluster, set the KUBECONFIG environment variable to this path. 

.. code-block:: bash

    $ export KUBECONFIG='~/.skyconf/clusters/cloud-cluster/kubeconfig' && kubectl get nodes

    NAME                                             STATUS   ROLES                       AGE     VERSION
    sky-cloud-cluster-0-4f9a-head-7xi46ifi-compute   Ready    control-plane,etcd,master   4m57s   v1.30.4+rke2r1
