.. _slurm_quickstart:

Quickstart - SkyFlow with Slurm
===============================

Congratulations on setting up SkyFlow with Slurm! 
You're on your way to simplifying and enhancing your job management and 
scheduling on Slurm clusters. Let's dive into how you can add, manage clusters, 
and submit jobs efficiently.

In this guide, we'll cover the following topics:

- Adding and removing Slurm Clusters from SkyFlow.
- Creating and running SkyFlow jobs on Slurm.

Prerequisites
+++++++++++++++++++++++++++++++
- SkyFlow API Server and Manager started:  :ref:`Setup Guide <setup>`.

- Configured Slurm Cluster configuration file: :ref:`Slurm Configuration guide <slurm_setup>`.


Adding and Removing Clusters
+++++++++++++++++++++++++++++++

Attaching a Remote Slurm Cluster
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

With SkyFlow, integrating a remote Slurm cluster into your workflow is straightforward. 
Start by ensuring the name of the cluster in the `slurmconf.yaml` configuration file matches the 
name you intend to use. Here's how you can attach it to SkyFlow:

.. code-block:: shell

    skyctl create cluster <slurmclustername> --manager slurm 

Now you're ready to deploy jobs to your Slurm cluster through SkyFlow!

Checking Cluster Status
^^^^^^^^^^^^^^^^^^^^^^^^

To view the status of your configured clusters, simply run:

.. code-block:: shell

    > skyctl get clusters

You'll see an output similar to the following, providing a snapshot of your clusters' resources and 
their status:

.. code-block:: none

    NAME            MANAGER    RESOURCES                          STATUS
    slurmcluster1   slurm      cpus: 520.0/600.0                  READY
                               memory: 1235171.0/3868184.0 MiB
                               P100: 8.0/8.0
    slurmcluster2   slurm      cpus: 420.0/600.0                  READY
                               memory: 1268431.0/2664184.0 MiB
    cluster3        k8s        cpus: 1.83/2.0                     READY
                               memory: 6035.6/7954.6 MiB

Detaching a Cluster
^^^^^^^^^^^^^^^^^^^

If you need to remove a cluster from SkyFlow, the process is just as simple:

.. code-block:: shell

    skyctl delete cluster <slurmclustername>

After detaching, you can verify the status of the remaining clusters with `skyctl get clusters` to see 
the updated list.

Submitting Jobs
+++++++++++++++

Submitting jobs through SkyFlow allows you to leverage the powerful scheduling and management 
capabilities of Slurm or Kubernetes, with the added benefits of SkyFlow's scheduling capabilities.

Creating a SkyFlow Job
^^^^^^^^^^^^^^^^^^^^^^

Here's an example SkyFlow job definition:

.. code-block:: yaml

    kind: Job

    metadata: 
      name: example-job
      labels:
        app: nginx

    spec:
      replicas: 2
      image: nginx:1.14.2
      resources:
        cpus: 0.5
        memory: 128
      ports:
        - 80
      restartPolicy: Always

To deploy this job, use the `skyctl apply` command with the job definition file:

.. code-block:: shell

    skyctl apply -f <path-to-your-job-file>.yaml

Alternative Job Creation Methods
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

SkyFlow also supports job creation via our Python API and the SkyFlow job CLI, offering you 
flexibility in how you manage your deployments. For instance, to create a job using the CLI:

.. code-block:: shell

    skyctl create job example-job --image nginx:1.14.2 --replicas 2 --cpus 0.5 --memory 128 --port 80 --labels app=nginx

Because this job requests 0.5 CPUs and 128 MiB of memory, it will be scheduled on a Slurm cluster as
the Kubernetes cluster has 0.17 CPUs available.

Monitoring Your Job
^^^^^^^^^^^^^^^^^^^^

To check the status of your jobs and ensure they're running as expected:

.. code-block:: shell

    > skyctl get jobs

    NAME          CLUSTER    REPLICAS    RESOURCES               NAMESPACE    STATUS
    example-job   slurmcluster1   2/2    cpus: 0.5               default      RUNNING
                                         memory: 128.0 MiB

You'll see details about each job, including the cluster it's running on, resources allocated, 
and its current status.

Now that you're equipped with the basics of managing clusters and jobs in SkyFlow using SLURM, 
you can start harnessing the full potential of your Slurm clusters. SkyFlow is designed to make your 
computational tasks easier, more efficient, and scalable. Happy computing!
