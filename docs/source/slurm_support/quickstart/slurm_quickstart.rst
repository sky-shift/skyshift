.. _slurm_quickstart:

Quickstart
==================

In this quickstart, we will walk through:

- Adding and removing Slurm Clusters from SkyFlow.
- Creating and running SkyFlow jobs on Slurm.
- Using SkyFlow CLI commands.

Note that this tutorial assumes that SkyFlow is already installed and running and the details of the remote Slurm cluster have been configured. If not, please refer to the :ref:`installation guide <installation>` and :ref:`setup guide <slurm_setup>`


Prerequisites
+++++++++++++++++++++++++++++++
- Configured Slurm Cluster configuration file: :ref:`Slurm Configuration guide <slurm_setup>`.

- SkyFlow API Server and Manager started:  :ref:`Setup Guide <setup>`.


Adding and Removing Clusters
+++++++++++++++++++++++++++++++

Attach a remote Slurm Cluster to SkyFlow. The provided cluster name must match the name provided inside the slurm configuration file.

.. code-block:: shell

  skyctl create cluster slurmclustername --manager slurm 

Check the status of existing clusters.

.. code-block:: shell

    > skyctl get clusters

    NAME               MANAGER    RESOURCES                          STATUS
    slurmcluster1        slurm    cpus: 520.0/600.0                  READY
                                  memory: 1235171.0/3868184.0 MiB
                                  P100: 8.0/8.0
    slurmcluster2        slurm    cpus: 420.0/600.0                  READY
                                  memory: 1268431.0/2664184.0 MiB
    cluster3              k8      cpus: 1.83/2.0                     READY
                                  memory: 6035.6/7954.6 MiB

Detach a cluster from SkyFlow.

.. code-block:: shell

  skyctl delete cluster slurmcluster1

Check the status of remaining clusters. Note that cluster3 is no longer listed, but is still running.

.. code-block:: shell

    > skyctl get clusters

    NAME               MANAGER    RESOURCES                          STATUS
    slurmcluster2        slurm    cpus: 420.0/600.0                  READY
                                  memory: 1268431.0/2664184.0 MiB
    cluster3              k8      cpus: 1.83/2.0                     READY
                                  memory: 6035.6/7954.6 MiB

Submitting Jobs
+++++++++++++++++++++++++++++++
Slurm job submission follows flow as SkyFlow job submissions.

The following is an example of a SkyFlow job:

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
    # Always restart a job's tasks, regardless of exit code.
    restartPolicy: Always

To create a SkyFlow job, run the following command:

.. code-block:: shell
  
    skyctl apply -f example-job.yaml

Alternatively, a SkyFlow job can be created via our Python API or the SkyFlow job CLI. Below, we demonstrate how to create a job using the SkyFlow job CLI.

.. code-block:: shell
  
    skyctl create job example-job --image nginx:1.14.2 --replicas 2 --cpus 0.5 --memory 128 --port 80 --labels app nginx
  

Note that, once a job is created, it will be automatically scheduled to run on one of the attached clusters. To check the status of the job, run the following command:

.. code-block:: shell

    > skyctl get jobs

    NAME          CLUSTER    REPLICAS    RESOURCES               NAMESPACE    STATUS
    example-job   slurmcluster1   2/2    cpus: 0.5               default      RUNNING
                                         memory: 128.0 MiB
