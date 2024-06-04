Executing Commands Within Resources
===================================

SkyShift’s CLI, `skyctl`, introduces the `exec` command, designed to execute 
specified commands within the containers of a resource. This command mirrors the 
functionality of Kubernetes' `kubectl exec`, offering the flexibility to run commands 
directly inside containers for debugging, monitoring, or operational purposes.
As of now, it only works with kubernetes resources, but support for other clusters
will be added in the future.

Creating an Execution Session
-----------------------------

The ``exec`` command facilitates command execution within a specified container of a 
resource, supporting both interactive and non-interactive sessions.

**Usage:**

.. code-block:: shell

    skyctl exec [OPTIONS] RESOURCE COMMAND...

**Options:**

- ``--namespace``: Specifies the namespace where the resource is located.
- ``-t, --tasks``: Targets specific tasks (akin to pods in Kubernetes) for command execution. This option can be repeated for multiple targets.
- ``-cts, --containers``: Specifies the container within the targeted tasks to execute the command. Multiple containers can be specified.
- ``-q, --quiet``: Suppresses the output from the command, only printing the final result.
- ``-it, --tty``: Opens an interactive terminal session, allowing for real-time interaction.

**Example:**

.. code-block:: shell

    skyctl exec myResource --namespace myNamespace -t myTask -cts myContainer -it -- /bin/bash

This command initiates an interactive terminal session within the `myContainer` 
container of the `myTask` task, part of the `myResource` resource in the `myNamespace` 
namespace, allowing the user to interact directly with a bash shell inside the container.

Role of the Command
-------------------

The `exec` command in SkyShift serves multiple purposes:

- **Debugging and Troubleshooting**: Quickly diagnose and resolve issues by running diagnostic commands or accessing logs within containers.
- **Operational Management**: Perform operational tasks such as database migrations, configuration changes, or updates directly within containers.
- **Interactive Sessions**: Open interactive sessions for educational purposes, manual interventions, or real-time monitoring.

**Note:**

Executing commands in containers should be done with consideration to the 
security and operational integrity of the environment. Interactive terminal 
sessions (`-it, --tty`) are particularly powerful and should be used judiciously, 
especially in production environments.

Security and remote execution
------------------------------------------

SkyShift follows a Role-Based Access Control (RBAC) system, which is detailed in 
the security section (to be added). This system ensures that only authorized users can 
perform actions like `exec`, based on their assigned roles and permissions.
