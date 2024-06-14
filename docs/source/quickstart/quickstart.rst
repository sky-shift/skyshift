.. _quickstart:

Quickstart
==================

In this quickstart, we will walk through:

- Adding and removing clusters from SkyShift.
- Creating and running SkyShift jobs.
- Using SkyShift CLI commands.

Note that this tutorial assumes that SkyShift is already installed and running. If not, please refer to the :ref:`installation guide <installation>`
and to the :ref:`setup guide <setup>` .


Prerequisites
+++++++++++++++++++++++++++++++
- Install `Kind <https://kind.sigs.k8s.io/docs/user/quick-start/>`_, a tool for running local Kubernetes clusters.


Adding and Removing Clusters
+++++++++++++++++++++++++++++++

Create 3 Kind clusters.

.. code-block:: shell

  for i in {1..3};
  do 
  kind create cluster --name cluster$i
  done

Attach provisioned clusters to SkyShift.

.. code-block:: shell

  for i in {1..3};
  do 
  skyctl create cluster cluster$i
  done

Check the status of existing clusters.

.. code-block:: shell

    > skyctl get clusters

    NAME               MANAGER    RESOURCES                          STATUS
    cluster1             k8       cpus: 1.83/2.0                     READY
                                  memory: 6035.6/7954.6 MiB
    cluster2             k8       cpus: 1.83/2.0                     READY
                                  memory: 6035.6/7954.6 MiB
    cluster3             k8       cpus: 1.83/2.0                     READY
                                  memory: 6035.6/7954.6 MiB

Detach a cluster from SkyShift.

.. code-block:: shell

  skyctl delete cluster cluster3

Check the status of remaining clusters. Note that cluster3 is no longer listed, but is still running.

.. code-block:: shell

    > skyctl get clusters

    NAME               MANAGER    RESOURCES                          STATUS
    cluster1             k8       cpus: 1.83/2.0                     READY
                                  memory: 6035.6/7954.6 MiB
    cluster2             k8       cpus: 1.83/2.0                     READY
                                  memory: 6035.6/7954.6 MiB

Submitting Jobs
+++++++++++++++++++++++++++++++

The following is an example of a SkyShift job:

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

To create a SkyShift job, run the following command:

.. code-block:: shell
  
    skyctl apply -f example-job.yaml

Alternatively, a SkyShift job can be created via our Python API or the SkyShift job CLI. Below, we demonstrate how to create a job using the SkyShift job CLI.

.. code-block:: shell
  
    skyctl create job example-job --image nginx:1.14.2 --replicas 2 --cpus 0.5 --memory 128 --port 80 --labels app nginx
  

Note that, once a job is created, it will be automatically scheduled to run on one of the attached clusters. To check the status of the job, run the following command:

.. code-block:: shell

    > skyctl get jobs

    NAME          CLUSTER    REPLICAS    RESOURCES               NAMESPACE    STATUS
    myservicejob  cluster1   2/2         cpus: 0.5               default      RUNNING
                                         memory: 128.0 MiB

Since a job is running on ``cluster1``, SkyShift observes fewer resources on ``cluster1``.

.. code-block:: shell

    > skyctl get clusters

    NAME               MANAGER    RESOURCES                          STATUS
    cluster1             k8       cpus: 0.93/2.0                     READY
                                  memory: 5779.6/7954.6 MiB
    cluster2            slurm     cpus: 1.83/2.0                     READY
                                  memory: 6035.6/7954.6 MiB