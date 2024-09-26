Links
========================

SkyShift's CLI, `skyctl`, offers a suite of commands for managing links between 
clusters, establishing bidirectional connections that enhance inter-cluster 
communication and service discovery. Details regarding how network communication is established is explained in `networking <../architecture/networking.rst>`_.
This section guides you through the creation, 
retrieval, and deletion of links, ensuring seamless connectivity across your clustered 
environment.

Creating a New Link
-------------------

The ``create link`` command initiates a new link between two specified clusters, 
enabling them to communicate directly with each other.

**Usage:**

.. code-block:: shell

    skyctl create link [OPTIONS] NAME

**Options:**

- ``--source, -s``: The name of the source cluster.
- ``--target, -t``: The name of the target cluster.

**Example:**

.. code-block:: shell

    skyctl create link myLink -s sourceCluster -t targetCluster

This command creates a new link named ``myLink`` between ``sourceCluster`` and ``targetCluster``, facilitating a pathway for bidirectional communication.

Retrieving Link Information
---------------------------

The ``get links`` command fetches details about one or all established links, 
providing insight into the connectivity configuration.

**Usage:**

.. code-block:: shell

    skyctl get link [OPTIONS] [NAME]

**Options:**

- ``--watch, -w``: Continuously monitor for changes in link status.

**Example:**

.. code-block:: shell

    skyctl get link myLink

Executing this command retrieves information about the link named ``myLink``. If no 
name is specified, it fetches details of all links.

Deleting a Link
---------------

The ``delete link`` command disbands a specified link between two clusters, 
severing the established connection.

**Usage:**

.. code-block:: shell

    skyctl delete link NAME

**Example:**

.. code-block:: shell

    skyctl delete link myLink

This command removes the link named ``myLink``, terminating the direct communication 
pathway between the associated clusters.

.. note:: The deletion of a link is a significant action that disrupts the connectivity between clusters. Proceed with caution to ensure continuity of service.

Future Enhancements
-------------------

Looking ahead, SkyShift aims to automate the creation of links, streamlining 
service discovery and inter-cluster communication. This advancement will enable tasks 
in different clusters within the same namespace to discover and communicate with each 
other effortlessly, further enhancing the flexibility and efficiency of managing 
distributed environments.

Links serve as critical infrastructure components in distributed systems, ensuring
that services across clusters can locate and interact with each other without manual 
configuration. By facilitating this level of interconnectivity, SkyShift empowers users
to architect more resilient, scalable, and interconnected applications.
