Jobs
=======================

SkyShift’s `skyctl` CLI equips users with a robust set of commands for managing jobs 
within clusters. These commands streamline the process of adding new jobs, fetching 
details or logs of existing jobs, and deleting jobs from SkyShift’s oversight. This 
section details the syntax, options, and examples for each job-related command, 
enhancing your ability to manage jobs effectively.

Creating a New Job
------------------

The ``create job`` command facilitates the addition of a new job to SkyShift, enabling 
job execution within the specified or default namespace, leveraging Docker images, and 
customizing resources.
The job will be scheduled to run on a specific cluster based on the specified resources and
replicas. In the future, SkyShift will take into account data locality among other factors to
schedule the job on the most suitable cluster.

**Usage:**

.. code-block:: shell

    skyctl create job [OPTIONS] NAME

**Options:**

- ``--namespace``: The job's namespace.
- ``-l, --labels``: Key-value pairs for job labels. Multiple labels can be specified.
- ``--image``: Docker image to use for the job.
- ``-e, --envs``: Environment variables for the job. Multiple variables can be specified.
- ``--cpus``: CPUs allocated per task.
- ``--gpus``: GPUs allocated per task.
- ``-a, --accelerators``: Specific accelerator resources to use.
- ``--memory``: Memory (RAM) allocated per task in MB.
- ``--run``: Command to run in the job.
- ``--replicas``: Number of job replicas.
- ``--restart_policy``: Job task restart policy.

**Example:**

.. code-block:: shell

    skyctl create job myJob --image ubuntu:latest --cpus 2 --memory 2048 --run "echo Hello, SkyShift!"

This command creates a new job named ``myJob``, using the ``ubuntu:latest`` image, 
with specified resources and a simple echo command as the job to run.

Retrieving Job Information
--------------------------

The ``get job`` command fetches details about a specific job or all jobs within a 
namespace.

**Usage:**

.. code-block:: shell

    skyctl get job [OPTIONS] [NAME]

**Options:**

- ``--namespace``: The job's namespace.
- ``-w, --watch``: Continuously watch for changes in the job's status.

**Example:**

.. code-block:: shell

    skyctl get job myJob

This command displays information about the job named ``myJob``. If no name is 
provided, it fetches details of all jobs in the default namespace. It will
provide information about the job's name, namespace, cluster, resources, replicas, status and age.

Fetching Job Logs
-----------------

The ``logs`` command retrieves the logs for a specified job, offering insights into job 
execution.

**Usage:**

.. code-block:: shell

    skyctl logs [OPTIONS] NAME

**Options:**

- ``--namespace``: The job's namespace.

**Example:**

.. code-block:: shell

    skyctl logs myJob

This command fetches and displays the logs for the job named ``myJob``.

Deleting a Job
--------------

The ``delete job`` command removes a job from SkyShift’s management and terminates its 
execution.

**Usage:**

.. code-block:: shell

    skyctl delete job NAME [OPTIONS]

**Options:**

- ``--namespace``: The job's namespace.

**Example:**

.. code-block:: shell

    skyctl delete job myJob

This command deletes the job named ``myJob`` from the specified or default namespace.

.. note:: The deletion of a job is irreversible; proceed with caution.

Validation and Constraints
--------------------------

- Job names and namespaces must adhere to DNS label standards, being no longer than 253 characters, and consisting of lower case alphanumeric characters or '-', and must start and end with an alphanumeric character.
- Labels follow the key-value pair format, with keys and values also adhering to DNS label standards.
- The image format validation ensures compatibility with Docker image naming conventions.
- Resource specifications for CPUs, GPUs, and memory must match the available resources in the cluster to ensure successful job execution.
- The restart policy determines the behavior of job replicas upon exit and must be one of the predefined policies supported by SkyShift.

These validations are crucial for maintaining the integrity and reliability of job management within SkyShift.