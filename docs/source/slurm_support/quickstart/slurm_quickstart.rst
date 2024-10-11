.. _slurm_quickstart:
===============================
Quickstart - SkyShift with Slurm
===============================

Congratulations on setting up SkyShift! 
You're on your way to simplifying and enhancing your job management and 
scheduling on Slurm clusters. Let's dive into how you can add, manage clusters, 
and submit jobs efficiently.

In this guide, we'll cover the following topics:

- Adding Slurm Cluster information in a simple YAML format
- Adding and removing Slurm Clusters from SkyShift.
- Creating and running SkyShift jobs on Slurm.

**Prerequisites**:
- SkyShift API Server and Manager:  :ref:`Setup Guide <setup>`.

Interfacing with Slurm Clusters
-------------------------------

Setting up the Config File
===============================

With SkyShift, integrating a remote Slurm Cluster into your workflow is straightforward. 
Copy the following YAML into :code:`~/.skyconf/slurm_config.yaml` file:

.. code-block:: yaml

  # Example of Slurm cluster accessed through CLI.
  SlurmCluster1: 
    interface: cli # Interfacing method SkyShift will use
    access_config: # Fields needed for SkyShift to reach the Cluster
      hostname: llama.millennium.berkeley.edu # SSH hostname of the Slurm node
      user: mluo # SSH Username 
      ssh_key: ~/berzerkeley # Local path to a RSA key
    # password: whatever

This defines a cluster with the following components:

- :code:`SlurmCluster1` : name of the Slurm Cluster, this needs to be unique for each cluster, but can be whatever you choose.

- :code:`interface` : the method SkyShift will use to access the cluster. Currently only `cli` is supported.

- :code:`access_config` : the login/security parameters needed for SkyShift to access the Slurm cluster.

- :code:`hostname` : SSH hostname used on the Slurm node.

- :code:`user` : username on the Slurm node.

- :code:`ssh_key` : local absolute path to private SSH key for remote authentiation with the Slurm node.

- :code:`password` : in the advent the Slurm cluster does not support SSH key authentiation, this password field can be added for password authentication(not recommended).

Once these fields are populated with your Slurm cluster's information, we can now attach it to SkyShift!

Attaching the Remote Slurm Cluster
===============================

With the configuration file fully populated with the details needed to access the Slurm Cluster, let's attach it to SkyShift.

Upon launch, SkyShift will automatically discover and attempt to attach all Slurm Clusters defined inside of `slurm_config.yaml`.
To launch SkyShift, run in :code:`skyshift/`:

.. code-block:: shell

  ./launch_skyshift.sh

If SkyShift is already running, attach the Slurm Cluster using the unique name given to it in the configuration step.

.. code-block:: shell

  skyctl create cluster SlurmCluster1 --manager slurm 

Checking Cluster Status
===============================

Before deploying a job to the Slurm Cluster, let's double check the status of your configured clusters, simply run:

.. code-block:: shell

    > skyctl get clusters

You'll see an output similar to the following, providing a snapshot of your clusters' resources and 
their status for job provisioning:

.. code-block:: none

    NAME            MANAGER    RESOURCES                          STATUS
    SlurmCluster1   slurm      cpus: 520.0/600.0                  READY
                               memory: 1235171.0/3868184.0 MiB
                               P100: 8.0/8.0
    cluster3        k8s        cpus: 1.83/2.0                     READY
                               memory: 6035.6/7954.6 MiB

Now you're ready to deploy jobs to your Slurm Cluster through SkyShift!

Submitting Jobs to Slurm
===============================

Submitting jobs to Slurm follows the same process as a standard SkyShift job, let's submit a simple test job to the Slurm Cluster.

.. code-block:: shell
  skyctl create job --cpus 1 --memory 128 --replicas 2 --run "echo hi; sleep 300; echo bye" my-test-job

Monitoring Your Job
===============================

To check the status of your jobs and ensure they're running as expected:

.. code-block:: shell

    > skyctl get jobs

    NAME          CLUSTER    REPLICAS    RESOURCES               NAMESPACE    STATUS
    my-test-job   SlurmCluster1   2/2    cpus: 1                 default      RUNNING
                                         memory: 128.0 MiB

You'll see details about each job, including the cluster it's running on, resources allocated, 
and its current status.

Detaching the Cluster
===============================

If you need to remove a cluster from SkyShift, the process is just as simple:

.. code-block:: shell

    skyctl delete cluster SlurmCluster1

.. note::

  If SkyShift is relaunched, it will automatically discover and attempt to attach all clusters defined in the configuration file. To prevent a cluster from being reattached, it will have to be removed from the configuration file.

After detaching, you can verify the status of the remaining clusters with :code:`skyctl get clusters` to see 
the updated list.

Now that you're equipped with the basics of managing clusters and jobs in SkyShift using Slurm, 
you can start harnessing the full potential of your Slurm clusters. SkyShift is designed to make your 
computational tasks easier, more efficient, and scalable. Happy computing!
