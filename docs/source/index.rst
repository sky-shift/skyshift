.. Skyflow documentation master file, created by
   sphinx-quickstart on Wed Mar 13 06:14:40 2024.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Overview
===================================

SkyFlow is a general-purpose container orchestration platform to deploy workloads *anywhere* - on any cloud provider, private cluster, or the edge. The vision of Skyflow is to complete the final layer of distributed computing - *automatically* managing the lifecycle of deployments, batch jobs, and services across multiple clusters.

SkyFlow abstracts many clusters into one large cluster. SkyFlow presents a thin layer on top of existing cluster managers, such as Kubernetes, Slurm, and other SkyFlows, which presents infinite scalability. SkyFlow accomplishes this with a unified job and service abstraction.

SkyFlow can flexibly breathe in and out resources as needed. SkyFlow can provision clusters on any cloud provider, and can be attached to any existing cluster with minimal administrator permissions. SkyFlow is designed to be lightweight and simple to install.

Finally, SkyFlow enforces security and isolation by independently managing authentication and role-based access control (RBAC) across clusters.

Documentation
==================

.. toctree::
   :maxdepth: 1
   :caption: Getting Started

   getting_started/installation.rst
   getting_started/setup.rst


.. toctree::
   :maxdepth: 1
   :caption: Quickstart

   quickstart/quickstart.rst

.. toctree::
   :maxdepth: 1
   :caption: Slurm Support
   
   slurm_support/overview.rst
   slurm_support/getting_started/slurm_setup.rst
   slurm_support/quickstart/slurm_quickstart.rst


