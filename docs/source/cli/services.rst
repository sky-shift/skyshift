Services
===========================

SkyShift's CLI, `skyctl`, introduces a set of commands tailored for creating, 
retrieving, and deleting services. Services in SkyShift mirror the functionality of 
Kubernetes services, providing a stable endpoint for accessing a dynamic set of jobs 
or tasks within a cluster (a task would be similar to a kubernetes pod). 
These commands are instrumental in defining how jobs are 
exposed within and across clusters, aligning with the broader orchestration and service
discovery mechanisms typical in cloud-native environments.

Creating a New Service
----------------------

The ``create service`` command provisions a new service within SkyShift, 
specifying how jobs are exposed based on label selectors and port mappings.

**Usage:**

.. code-block:: shell

    skyctl create service [OPTIONS] NAME

**Options:**

- ``--namespace``: Designates the namespace where the service will be created.
- ``-t, --service_type``: Specifies the type of service (e.g., ClusterIP).
- ``-s, --selector``: Label selectors for targeting jobs.
- ``-p, --ports``: Port mappings for the service (port:targetPort).
- ``-c, --cluster``: Specifies the cluster to expose the service on.

**Example:**

.. code-block:: shell

    skyctl create service myService -t ClusterIP -s app=myApp -p 80:8080 -c myCluster

This command creates a new service named ``myService`` in the default namespace, 
targeting jobs labeled `app=myApp`, mapping external port 80 to container port 8080, 
and exposed on the `myCluster` cluster.
SkyShift provides a unified service endpoint hosted at  `myCluster`, and manages the `inter-cluster networking <../architecture/networking.rst>`_.
to load balance the requests to `myApp` regardless of the clusters where its replicas are running.

Retrieving Service Information
------------------------------

The ``get service`` command fetches details about one or all services within a 
specified namespace, offering insights into the service configurations and their 
selectors.

**Usage:**

.. code-block:: shell

    skyctl get service [OPTIONS] [NAME]

**Options:**

- ``--namespace``: The service's namespace.
- ``--watch``: Enables real-time monitoring of the service's status.

**Example:**

.. code-block:: shell

    skyctl get service myService

This command retrieves information about the service named ``myService``. Without 
specifying a name, it returns details of all services in the given namespace.

Deleting a Service
------------------

The ``delete service`` command removes a specified service from SkyShift, terminating 
its endpoint and ceasing any network exposure to the targeted jobs.

**Usage:**

.. code-block:: shell

    skyctl delete service NAME [OPTIONS]

**Options:**

- ``--namespace``: The service's namespace.

**Example:**

.. code-block:: shell

    skyctl delete service myService

This command deletes the service named ``myService`` from its namespace, effectively 
removing the defined network access to the selected jobs.

.. note:: Deleting a service is irreversible and impacts the network accessibility of the associated jobs. Ensure that the service is no longer required before proceeding with deletion.

Understanding SkyShift Services
-------------------------------

Services in SkyShift serve as the backbone for network communication within the 
platform, akin to Kubernetes services. They allow for:

- **Stable Networking Endpoints**: Services provide a consistent way to access a dynamic set of jobs, regardless of the individual lifecycles of those jobs.
- **Flexible Job Discovery**: By utilizing label selectors, services facilitate discovery and communication among jobs that meet the specified criteria.
- **Load Balancing and Port Mapping**: Services abstract the complexity of port management and load balancing, ensuring that network traffic is distributed evenly across the targeted jobs.