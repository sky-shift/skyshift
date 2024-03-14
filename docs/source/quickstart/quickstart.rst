.. _quickstart:

Quickstart
==================

In this quickstart, we will walk through:

- Adding and removing clusters from SkyFlow.
- Creating and running SkyFlow jobs.
- Using SkyFlow CLI commands.

Note that this tutorial assumes that SkyFlow is already installed and running. If not, please refer to the :ref:`installation guide <installation>`.

+++++++++++++++
Prerequisites
+++++++++++++++
- Install `Kind <https://kind.sigs.k8s.io/docs/user/quick-start/>`_, a tool for running local Kubernetes clusters.


+++++++++++++++
Adding and Removing Clusters
+++++++++++++++

Create 3 kind Kubernetes clusters.

.. code-block:: shell

  for i in {1..3};
  do 
  kind create cluster --name cluster$i
  done

Add the clusters to SkyFlow.

.. code-block:: shell

  for i in {1..3};
  do 
  skyctl create cluster --name cluster$i --attached
  done

Check the status of existing clusters in SkyFlow.

.. code-block:: shell

    NAME               MANAGER    RESOURCES                          STATUS
    cluster1             k8       cpus: 1.83/2.0                     READY
                                memory: 6035.6/7954.6 MiB
    cluster2             k8       cpus: 1.83/2.0                     READY
                                memory: 6035.6/7954.6 MiB
    cluster3             k8       cpus: 1.83/2.0                     READY
                                memory: 6035.6/7954.6 MiB

