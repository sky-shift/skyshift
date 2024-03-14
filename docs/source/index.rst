.. Skyflow documentation master file, created by
   sphinx-quickstart on Wed Mar 13 06:14:40 2024.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

What is SkyFlow?
===================================

SkyFlow is a general-purpose container orchestration platform to deploy workloads *anywhere* - on any cloud, cluster, or cluster manager. SkyFlow's vision is to complete the final layer distributed computing - *automatically* managing the lifecycle of deployments, batch jobs, and services across multiple clusters.

SkyFlow abstracts many clusters into one super cluster. SkyFlow presents a thin layer on top of existing cluster managers, such as Kubernetes, SLURM, and other SkyFlows, which presents infinite scalability. SkyFlow accomplishes this with a unified job and service abstraction that is simple and easy to learn. 

SkyFlow can flexibly breathe in and out resources as needed. SkyFlow can provision clusters on any cloud provider, and can easily be attached to any cluster without need for adminstrator permissions. SkyFlow is designed to be lightweight and easy to install, with a small footprint and minimal dependencies.

SkyFlow independently manages authentication and role-based access control (RBAC) across clusters, providing a single pane of glass for managing all clusters as one cluster. 

Documentation
==================

.. toctree::
   :maxdepth: 1
   :caption: Getting Started

   getting_started/installation.rst