.. _architecture:

SkyShift Architecture
======================

SkyShift's system architecture is designed to be highly modular, scalable, and flexible. It employs a controller-based architecture that orchestrates various components to manage the lifecycle of deployments and services across multiple clusters.

.. image:: /_static/skyshift-architecture.svg
  :width: 100%
  :align: center
  :alt: SkyShift Architecture Diagram
  :class: no-scaled-link, only-dark

SkyShift's architecture consists of the following components:

- **ETCD**: A distributed, reliable key-value store that provides a robust datastore for SkyShift objects.
- **API server**: The central API server that utilizes FastAPI to provide create, read, update, delete, and watch operations over SkyShift objects. The API server is the central interface for both users and controllers.
- **Controller Manager**: Manages various higher-level controllers that make decisions across clusters.

Within the controller manager, the following higher-level controllers are responsible for managing different aspects of the system:

- **Scheduler**: Responsible for scheduling jobs. It automatically determines the spread of jobs across clusters. This controller is resource-aware and can be easily customized with different scheduling plugins.
- **Skylet Manager**: Creates and deletes Skylets, which represent an abstracted view of a cluster or a set of clusters. Skylets monitor the state of the cluster and manage the lifecycle of the cluster.
- **Provisioner**: Manages the provisioning and scaling of clusters across multiple regions and clouds. The provisoiner controller uses Skypilot under the hood.

Skylet represents an abstracted interface to manage the lifecycle of a cluster or a set of clusters. Within each Skylet, there are various controllers that manage different aspects of the cluster. Below, we describe a subset of these controllers:

- **Cluster Controller**: Monitors the cluster state.
- **Job Controller**: Monitors the state of SkyShift-submitted jobs.
- **Service Controller**: Monitors the state of SkyShift-submitted services.
- **Flow Controller**: Creates, updates, and deletes jobs and services on the cluster.
- **Network Controller**: Manages the endpoints for services that span across clusters.

Most importantly, SkyShift's compatibility layer abstracts the underlying cluster manager's specific APIs into a common interface. This allows SkyShift to interact with different cluster managers like Kubernetes and Slurm,  managing workloads across multiple clusters regardless of the underlying cluster manager.