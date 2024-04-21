Namespaces
=============================

The SkyFlow CLI, `skyctl`, includes commands for managing namespaces, enabling 
users to create, retrieve, and delete namespaces efficiently. Namespaces are pivotal 
for organizing resources within SkyFlow, allowing for segregated environments within a 
single cluster. This section provides guidance on the usage, options, and examples for 
namespace-related commands.

Creating a New Namespace
------------------------

The ``create namespace`` command establishes a new namespace within SkyFlow, 
offering a segregated space for resource management.

**Usage:**

.. code-block:: shell

    skyctl create namespace NAME

**Parameters:**

- ``NAME``: The name of the namespace to create. It must comply with DNS label standards—no longer than 253 characters, consisting of lower case alphanumeric characters or '-', and must start and end with an alphanumeric character.

**Example:**

.. code-block:: shell

    skyctl create namespace myNamespace

This command creates a new namespace named ``myNamespace`` in SkyFlow.

Retrieving Namespace Information
--------------------------------

The ``get namespace`` command fetches details about one or all namespaces within 
SkyFlow.

**Usage:**

.. code-block:: shell

    skyctl get namespace [OPTIONS] [NAME]

**Options:**

- ``-w, --watch``: Continuously monitor for changes in the namespace's status.

**Example:**

.. code-block:: shell

    skyctl get namespace myNamespace

This command displays information about the namespace named ``myNamespace``. If no 
name is provided, it retrieves details of all namespaces.

Deleting a Namespace
--------------------

The ``delete namespace`` command eradicates a namespace from SkyFlow. This action 
removes the namespace and all resources within it from management.

**Usage:**

.. code-block:: shell

    skyctl delete namespace NAME

**Parameters:**

- ``NAME``: The name of the namespace to delete.

**Example:**

.. code-block:: shell

    skyctl delete namespace myNamespace

This command deletes the namespace named ``myNamespace`` from SkyFlow.

.. note:: Deletion of a namespace is an irreversible action that also removes all resources contained within it. Exercise caution when performing this operation.

Validation and Constraints
--------------------------

- The namespace name must adhere to DNS label standards to ensure compatibility with Kubernetes naming conventions. This validation promotes consistency and avoids conflicts within SkyFlow and the underlying Kubernetes cluster.