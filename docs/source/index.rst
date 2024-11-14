.. SkyShift documentation master file, created by
   sphinx-quickstart on Wed Mar 13 06:14:40 2024.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Overview
===================================

SkyShift is a general-purpose container orchestration platform to deploy workloads *anywhere* - on any cloud provider, private cluster, or the edge. The vision of SkyShift is to complete the final layer of distributed computing - *automatically* managing the lifecycle of deployments, batch jobs, and services across multiple clusters.

SkyShift abstracts many clusters into one large cluster. SkyShift presents a thin layer on top of existing cluster managers, such as Kubernetes, Slurm, and other SkyShifts, which presents infinite scalability. SkyShift accomplishes this with a unified job and service abstraction.

SkyShift can flexibly breathe in and out resources as needed. SkyShift can provision clusters on any cloud provider, and can be attached to any existing cluster with minimal administrator permissions. SkyShift is designed to be lightweight and simple to install.

Finally, SkyShift enforces security and isolation by independently managing authentication and role-based access control (RBAC) across clusters.

Documentation
==================

.. toctree::
   :maxdepth: 1
   :caption: Core Concepts

   Architecture <architecture/architecture.rst>
   Networking <architecture/networking.rst>
   
.. toctree::
   :maxdepth: 1
   :caption: Getting Started

   getting_started/installation.rst
   getting_started/setup.rst
   getting_started/cli_docs.rst

.. toctree::
   :maxdepth: 1
   :caption: Quickstart

   quickstart/quickstart.rst

.. toctree::
   :maxdepth: 1
   :caption: Registration and Login

   authentication/authentication.rst

.. toctree::
   :maxdepth: 1
   :caption: Slurm Support
   
   slurm_support/overview.rst
   slurm_support/getting_started/slurm_setup.rst
   slurm_support/quickstart/slurm_quickstart.rst

.. toctree::
   :maxdepth: 1
   :caption: Ray Support
   
   ray/quickstart/ray_quickstart.rst
   ray/overview.rst


.. toctree::
   :maxdepth: 1
   :caption: Kubernetes Support
   
   kubernetes_support/overview.rst
   kubernetes_support/cloud.rst


.. toctree::
   :maxdepth: 1
   :caption: Using SkyShift

   cli/clusters.rst
   cli/jobs.rst
   cli/namespaces.rst
   cli/filterpolicies.rst
   cli/links.rst
   cli/services.rst
   cli/endpoints.rst
   cli/roles.rst
   cli/exec.rst
   cli/users.rst

.. toctree::
   :maxdepth: 1
   :caption: Examples

   examples/bookinfo.rst
   examples/vllm.rst