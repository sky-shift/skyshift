SkyShift CLI Overview
======================

Welcome to the SkyShift CLI documentation. The SkyShift Command Line Interface (CLI), `skyctl`, can be used to manage
and orchestrate your SkyShift environment. Keep reading to go through the CLI's capabilities, the components it manages,
and how you can leverage it for your operations.

What is the SkyShift CLI?
-------------------------

The SkyShift CLI serves is the command-line interface for managing infrastructure and services within SkyShift.
Used for actions like deploying clusters, managing jobs, setting up services, or controlling access via role-based
permissions.

With `skyctl`, you can:
- **Provision and manage clusters** on various cloud providers.
- **Deploy and monitor jobs** running on these clusters.
- **Expose services** to enable communication between applications and users.
- **Organize resources** into namespaces for logical separation and management.
- **Control traffic flow** between services and clusters using endpoints and links.
- **Define and enforce access control** with roles and policies.
- **Manage users and authentication** within your environment.

Below, we go through the core functionalities of SkyShift and link to specific documentation for each component.

Core Functionalities
--------------------

1. Cluster Management
~~~~~~~~~~~~~~~~~~~~~

Clusters are the fundamental units of compute resources for SkyShift. The SkyShift CLI allows you to
create, monitor, and manage these clusters. You can specify the number of nodes, CPU and memory
allocations, and even choose between different cluster managers like Kubernetes/Slurm/Ray.

- **Create a Cluster**: Attach new clusters to SkyShift, either by provisioning them on a cloud provider or by attaching existing ones.
- **Monitor Cluster**: Retrieve detailed information about cluster status, including resource allocation and availability.
- **Delete Clusters**: Safely remove clusters from SkyShift management and optionally from the cloud provider.

**Documentation**: :doc:`clusters`

2. Job Management
~~~~~~~~~~~~~~~~~

Jobs are the tasks or workloads that run on your clusters. The SkyShift CLI provides commands
to submit, monitor, and manage these jobs.

- **Submit Jobs**: Deploy new jobs to your clusters, specifying resources like CPUs, memory, and accelerators.
- **Monitor Jobs**: Track job progress, and retrieve status updates.
- **Manage Job Lifecycle**: Scale, restart, or delete jobs as needed.

**Documentation**: :doc:`jobs`

3. Service Management
~~~~~~~~~~~~~~~~~~~~~

Services in SkyShift are used to expose your applications, enabling communication between internal
components or with external users.

- **Create Services**: Define services to manage network traffic, load balancing, and service discovery.
- **Monitor Services**: Retrieve information about existing services, including endpoints and health status.
- **Delete Services**: Remove services that are no longer needed, ensuring clean and efficient resource management.

**Documentation**: :doc:`services`

4. Namespace Management
~~~~~~~~~~~~~~~~~~~~~~~

Namespaces provide a way to logically organize your resources within SkyShift, enabling multi-tenancy and
efficient resource management.

- **Create Namespaces**: Organize your resources by creating namespaces tailored to different teams, environments, or projects.
- **Manage Namespace Resources**: Assign resources to specific namespaces and monitor their usage.
- **Delete Namespaces**: Clean up unused namespaces to maintain an organized environment.

**Documentation**: :doc:`namespaces`

5. Endpoint Management
~~~~~~~~~~~~~~~~~~~~~~

Endpoints are used to control the flow of traffic between different services and clusters. The SkyShift CLI
allows you to define and manage these endpoints.

- **Create Endpoints**: Set up endpoints to route traffic between clusters or services.
- **Monitor Endpoints**: Ensure that endpoints are functioning correctly and efficiently.
- **Delete Endpoints**: Remove endpoints that are no longer required to simplify your network topology.

**Documentation**: :doc:`endpoints`

6. Link Management
~~~~~~~~~~~~~~~~~~

Links create connections between clusters, allowing resources in one cluster
to communicate with resources in another.

- **Create Links**: Establish links between clusters to enable cross-cluster communication.
- **Manage Links**: Monitor and modify links as your infrastructure evolves.
- **Delete Links**: Tear down unnecessary links to maintain a clean network architecture.

**Documentation**: :doc:`links`

7. Filter Policies
~~~~~~~~~~~~~~~~~~~~~~

Filter policies allow you to define rules for selecting and filtering clusters
or other resources based on labels and other criteria.

- **Define Filter Policies**: Create policies that automatically select clusters or resources based on defined criteria.
- **Apply Policies**: Enforce these policies across your environment to streamline resource management.
- **Manage Policies**: Update or delete policies as your requirements change.

**Documentation**: :doc:`filterpolicies`

8. Role-Based Access Control (RBAC)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

RBAC is essential for managing permissions and access within SkyShift. The CLI provides tools
to define roles and assign permissions to users or groups.

- **Create Roles**: Define roles that encapsulate specific permissions for accessing resources.
- **Assign Roles**: Attach roles to users or groups to enforce access control.
- **Manage Roles**: Update or revoke roles as your security policies evolve.

**Documentation**: :doc:`roles`

9. User Management
~~~~~~~~~~~~~~~~~~~~~

User management is a crucial aspect of maintaining security and access control within SkyShift.

- **Add Users**: Register new users within SkyShift, setting up their authentication and permissions.
- **Manage Users**: Update user details, reset passwords, or deactivate accounts.

**Documentation**: :doc:`users`

10. Command Execution
~~~~~~~~~~~~~~~~~~~~~~~~~

The SkyShift CLI also provides the ability to execute commands directly within managed resources,
facilitating direct interaction with your infrastructure.

- **Execute Commands**: Run commands within your clusters or services directly from the CLI.
- **Interactive Sessions**: Use TTY mode for interactive command sessions.
- **Manage Output**: Control the verbosity and output format of command execution.


Additional Features
~~~~~~~~~~~~~~~~~~~

While the primary functionalities of SkyShift are covered in the sections above, the CLI also includes various
utility commands and configuration options that enhance the usability.

- **Context Management**: Switch between different SkyShift environments or contexts to manage multiple deployments.
- **Logging Configuration**: Customize logging settings to capture detailed information about CLI operations.

Getting Started with SkyShift CLI
---------------------------------

To begin using the SkyShift CLI, follow these steps:

1. **Install the CLI**: Ensure that `skyctl` is installed on your machine and properly configured with access to your SkyShift environment.
2. **Create Your First Cluster**: Follow the cluster management guide to provision your first cluster and start deploying jobs and services.

For more detailed instructions, refer to the specific sections linked above.
