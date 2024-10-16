.. _clustercli:

Clusters
===========================

SkyShift, through its command-line interface (CLI), `skyctl`, offers a comprehensive 
suite of commands for efficient cluster management. These commands facilitate the 
attachment of new clusters, the retrieval of details about existing clusters, and the 
removal of clusters from SkyShift's oversight. This document delineates the usage, 
options, and examples pertinent to each command, ensuring you can leverage SkyShift to 
its fullest potential.

Creating a New Cluster
----------------------

The ``create cluster`` command facilitates the integration of a new cluster into 
SkyShift for seamless management. This command is versatile, allowing for the creation 
of a cluster on your chosen cloud provider with designated resources, or for the 
attachment of an existing cluster to SkyShift. The command supports clusters managed by 
Kubernetes or Slurm.

**Usage:**

.. code-block:: shell

    skyctl create cluster [OPTIONS] NAME

**Options:**

- ``--manager``: Denotes the type of cluster manager (e.g., k8, slurm), with ``k8`` as the default.
- ``--cpus``: Specifies the number of vCPUs per node (e.g., 0.5, 1, 1+).
- ``--memory``: Determines the memory requirement per instance in GB (e.g., 32, 32+).
- ``--disk_size``: Sets the OS disk size in GB.
- ``--accelerators``: Identifies the type and number of GPU accelerators to utilize.
- ``--ports``: Lists the ports to be opened on the cluster. Multiple ports can be declared.
- ``--num_nodes``: Allocates the number of SkyPilot nodes to the cluster, with 1 as the default.
- ``--cloud``: Specifies the cloud provider.
- ``--region``: Defines the cloud region.
- ``--provision``: Triggers the provisioning of the cluster on the cloud if set.

**Example:**

.. code-block:: shell

    skyctl create cluster myCluster --manager k8 --cpus 4 --memory 16 --disk_size 100 --num_nodes 3 --cloud aws --region us-west-2 --provision

This command initiates the creation of a new cluster named ``myCluster``, managed by 
Kubernetes. It provisions the cluster on AWS in the US West (Oregon) region, 
configuring 3 nodes each with 4 vCPUs, 16 GB of memory, and a 100 GB OS disk. 
Post-creation, SkyShift connects to the cluster and commences status monitoring.

Retrieving Cluster Information
------------------------------

The ``get cluster`` command fetches and displays details for one or all clusters under 
SkyShift management, including names, managers, statuses, and resources (both allocated 
and available).

**Usage:**

.. code-block:: shell

    skyctl get cluster [OPTIONS] [NAME]

**Options:**

- ``--watch, -w``: Enables continuous monitoring of the cluster's status.

**Example:**

.. code-block:: shell

    skyctl get cluster myCluster

Executing this command will reveal details about the cluster named ``myCluster``. 
Omitting the name argument will yield information on all clusters managed by SkyShift.

Deleting a Cluster
-------------------

The ``delete cluster`` command extricates a cluster from SkyShift’s management framework. For clusters provisioned by SkyShift, this command also orchestrates their removal from the corresponding cloud provider.

**Usage:**

.. code-block:: shell

    skyctl delete cluster NAME

**Example:**

.. code-block:: shell

    skyctl delete cluster myCluster

By executing this command, the cluster named ``myCluster`` is detached from SkyShift 
and expunged from the cloud provider, contingent on its SkyShift-provisioned status.

.. note:: Exercise caution when invoking the ``delete`` command; it irrevocably disassociates the cluster from SkyShift’s management and, if applicable, eradicates it from the cloud.
   