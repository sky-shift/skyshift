Filter Policies
=================================

SkyShift’s CLI, `skyctl`, provides a specialized set of commands for managing 
FilterPolicies. These policies enable refined control over where jobs can be 
scheduled, akin to node taints in Kubernetes but applied across clusters. 
FilterPolicies can be defined to include or exclude clusters from job scheduling 
based on labels or explicit cluster names, facilitating adherence to data sovereignty 
requirements, company-specific policies, or other operational constraints.

Creating a New Filter Policy
----------------------------

The ``create filterPolicy`` command introduces a new filter policy into SkyShift, 
dictating the scheduling eligibility of clusters based on the specified inclusion and 
exclusion criteria.

**Usage:**

.. code-block:: shell

    skyctl create filterPolicy [OPTIONS] NAME

**Options:**

- ``--namespace``: Specifies the namespace where the policy will reside.
- ``-l, --labelSelector``: Key-value pairs for selecting clusters based on labels.
- ``-i, --includeCluster``: Explicitly lists the clusters to include in scheduling.
- ``-e, --excludeCluster``: Explicitly lists the clusters to exclude from scheduling.

**Example:**

.. code-block:: shell

    skyctl create filterPolicy myPolicy --namespace myNamespace -l key1=value1 -i includedCluster -e excludedCluster

This command creates a new filter policy named ``myPolicy`` in the ``myNamespace`` namespace. It includes clusters labeled with `key1=value1`, specifically includes `includedCluster`, and excludes `excludedCluster`.

Retrieving Filter Policy Information
------------------------------------

The ``get filterPolicy`` command fetches details of one or all filter policies within 
a namespace.

**Usage:**

.. code-block:: shell

    skyctl get filterPolicy [OPTIONS] [NAME]

**Options:**

- ``--namespace``: The policy's namespace.
- ``--watch``: Continuously monitor for changes in the policy's status.

**Example:**

.. code-block:: shell

    skyctl get filterPolicy myPolicy

This command retrieves information about the filter policy named ``myPolicy``. 
Omitting the name fetches details of all filter policies in the specified or default 
namespace.

Deleting a Filter Policy
-------------------------

The ``delete filterPolicy`` command removes a specified filter policy from SkyShift.

**Usage:**

.. code-block:: shell

    skyctl delete filterPolicy NAME [OPTIONS]

**Options:**

- ``--namespace``: The policy's namespace.

**Example:**

.. code-block:: shell

    skyctl delete filterPolicy myPolicy

This command deletes the filter policy named ``myPolicy`` from its namespace.

.. note:: Deletion of a filter policy is irreversible and should be executed with careful consideration of its impact on job scheduling.
