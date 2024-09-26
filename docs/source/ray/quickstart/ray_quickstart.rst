.. _ray_quickstart:

Quickstart - SkyShift with Ray
===============================

You're on your way to simplifying and enhancing your job management and 
scheduling on Ray clusters. Let's dive into how you can add, manage clusters, 
and submit jobs efficiently.

In this guide, we'll cover the following topics:

- Adding and removing Ray Clusters from SkyShift.
- Creating and running SkyShift jobs on Ray.

Prerequisites
+++++++++++++++++++++++++++++++

- Open Ports:
    - The following ports need to be open on the target cluster for communication:
        - `RAY_CLIENT_PORT`: 10001
        - `RAY_JOBS_PORT`: 8265
        - `RAY_DASHBOARD_PORT`: 8265
        - `RAY_NODES_PORT`: 6379
    - If Ray needs to be installed, port 22 must also be open for SSH access.

- Connection details for the Ray cluster:
    - If Ray needs to be installed:
        - `ssh_key_path`: Path to the SSH private key.
        - `username`: Username for the SSH connection.
    - `host`: Hostname or IP address of the target cluster.

Automatic Ray Installation
+++++++++++++++++++++++++++

If Ray is not installed on the target cluster, SkyShift can automatically install it using the `ray_install.sh` script. The script installs Miniconda, creates a new Conda environment, and installs Ray. This ensures that the necessary components are in place for job submission and management without requiring manual intervention from the user.

Adding and Removing Clusters
+++++++++++++++++++++++++++++++

Attaching a Remote Ray Cluster
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

With SkyShift, integrating a remote Ray cluster into your workflow is straightforward. 
Start by ensuring the name of the cluster in the `rayconf.yaml` configuration file matches the 
name you intend to use. Here's how you can attach it to SkyShift:

.. code-block:: shell

    skyctl create cluster <rayclustername> --manager ray 

Now you're ready to deploy jobs to your Ray cluster through SkyShift!

Checking Cluster Status
^^^^^^^^^^^^^^^^^^^^^^^^

To view the status of your configured clusters, simply run:

.. code-block:: shell

    > skyctl get clusters

You'll see an output similar to the following, providing a snapshot of your clusters' resources and 
their status:

.. code-block:: none

    NAME            MANAGER    RESOURCES                          STATUS
    raycluster1     ray        cpus: 520.0/600.0                  READY
                               memory: 1235171.0/3868184.0 MiB
                               P100: 8.0/8.0
    raycluster2     ray        cpus: 420.0/600.0                  READY
                               memory: 1268431.0/2664184.0 MiB
    cluster3        k8s        cpus: 1.83/2.0                     READY
                               memory: 6035.6/7954.6 MiB

Detaching a Cluster
^^^^^^^^^^^^^^^^^^^

If you need to remove a cluster from SkyShift, the process is just as simple:

.. code-block:: shell

    skyctl delete cluster <rayclustername>

After detaching, you can verify the status of the remaining clusters with `skyctl get clusters` to see 
the updated list.

Submitting Jobs
+++++++++++++++

Submitting jobs through SkyShift allows you to leverage the powerful scheduling and management 
capabilities of Ray, SLURM or Kubernetes, with the added benefits of SkyShift's scheduling capabilities.

Creating a SkyShift Job
^^^^^^^^^^^^^^^^^^^^^^

Here's an example SkyShift job definition:

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

SkyShift also supports job creation via our Python API and the SkyShift job CLI, offering you 
flexibility in how you manage your deployments. For instance, to create a job using the CLI:

.. code-block:: shell

    skyctl create job example-job --image nginx:1.14.2 --replicas 2 --cpus 0.5 --memory 128 --port 80 --labels app=nginx

Because this job requests 0.5 CPUs and 128 MiB of memory, it will be scheduled on a Ray cluster as
the Kubernetes cluster has 0.17 CPUs available.

Monitoring Your Job
^^^^^^^^^^^^^^^^^^^^

To check the status of your jobs and ensure they're running as expected:

.. code-block:: shell

    > skyctl get jobs

    NAME          CLUSTER    REPLICAS    RESOURCES               NAMESPACE    STATUS
    example-job   raycluster1   2/2      cpus: 0.5               default      RUNNING
                                         memory: 128.0 MiB

You'll see details about each job, including the cluster it's running on, resources allocated, 
and its current status.

Now that you're equipped with the basics of managing clusters and jobs in SkyShift using Ray, 
you can start harnessing the full potential of your Ray clusters. SkyShift is designed to make your 
computational tasks easier, more efficient, and scalable. Happy computing!
