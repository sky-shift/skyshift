Endpoints
=============================

SkyShift's CLI, `skyctl`, includes commands for managing endpoints, which are crucial 
for defining the network connectivity for services within SkyShift. Endpoints can be 
explicitly exposed to the cluster, allowing for external access. This section details 
the commands to create, view, and delete endpoint configurations, streamlining the 
management of network entry points for services and jobs.

Creating New Endpoints
----------------------

The ``create endpoints`` command facilitates the creation of a new set of endpoints, 
specifying how services within SkyShift can access external networks or how they are 
accessed from outside.

**Usage:**

.. code-block:: shell

    skyctl create endpoints [OPTIONS] NAME

**Options:**

- ``--namespace``: Specifies the namespace where the endpoints will be created.
- ``--num_endpoints``: Defines the number of endpoints.
- ``--exposed``: Marks the endpoints as exposed to the cluster if set.
- ``--primary_cluster``: Indicates the primary cluster where the endpoints are to be exposed.
- ``--selector``: Selector key-value pairs for targeting specific services or jobs.

**Example:**

.. code-block:: shell

    skyctl create endpoints myEndpoints --namespace myNamespace --num_endpoints 3 --exposed --primary_cluster myCluster -s key1=value1

This command creates a set of endpoints named ``myEndpoints`` in the ``myNamespace`` namespace, comprising three endpoints exposed within the ``myCluster`` cluster and targeted using the selector `key1=value1`.

Retrieving Endpoint Information
-------------------------------

The ``get endpoints`` command fetches details about a specific set of endpoints or all 
endpoints within a namespace.

**Usage:**

.. code-block:: shell

    skyctl get endpoints [OPTIONS] [NAME]

**Options:**

- ``--namespace``: The namespace of the endpoints.
- ``--watch``: Enables real-time monitoring of the endpoints' status.

**Example:**

.. code-block:: shell

    skyctl get endpoints myEndpoints

Executing this command retrieves information about the endpoints named ``myEndpoints``. Without a name, it returns details of all endpoints in the specified or default namespace.

Deleting Endpoints
------------------

The ``delete endpoints`` command removes a specified set of endpoints from SkyShift, 
eliminating the configured network access points.

**Usage:**

.. code-block:: shell

    skyctl delete endpoints NAME [OPTIONS]

**Options:**

- ``--namespace``: The namespace of the endpoints.

**Example:**

.. code-block:: shell

    skyctl delete endpoints myEndpoints

This command deletes the endpoints named ``myEndpoints``, ceasing their network 
exposure and connectivity configurations.

.. note:: Deletion of endpoints is irreversible. Ensure that the endpoints are no longer required for network communication before proceeding with deletion.

Understanding SkyShift Endpoints
--------------------------------

Endpoints in SkyShift are analogous to Kubernetes endpoints, acting as network conduits 
either into or out of services and jobs. They play a vital role in:

- **Facilitating External Access**: Exposed endpoints allow services within SkyShift to be accessible from outside the cluster, enabling integration with external systems or users.
- **Enabling Internal Connectivity**: Endpoints can also be configured to allow services within SkyShift to reach out to external resources, supporting a wide range of communication patterns and use cases.
