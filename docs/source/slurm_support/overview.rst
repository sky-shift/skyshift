Overview
========

SkyShift: Revolutionizing Job Management on Slurm Clusters
---------------------------------------------------------

SkyShift stands at the forefront of job management, seamlessly integrating with Slurm Clusters to 
offer an intuitive, powerful interface for managing computational tasks. Slurm, the renowned 
open-source, fault-tolerant, and highly scalable cluster management and job scheduling system, 
caters to a wide range of Linux clusters. From colossal supercomputers to modest compute farms, 
Slurm's versatility shines in allocating resources, orchestrating job execution, and efficiently 
managing queues of pending tasks. Discover the expansive capabilities of 
Slurm `here <https://slurm.schedmd.com/>`_.

Empowering Researchers and Engineers
-------------------------------------

SkyShift's integration with Slurm opens new horizons for researchers and engineers, allowing for 
effortless submission of jobs to leading-edge supercomputers like `NERSC <https://www.nersc.gov/>`_, 
as well as to compute farms maintained by various institutions or individual enthusiasts. This level 
of flexibility ensures that your computational research and engineering tasks are executed 
efficiently, leveraging the best available resources.

Uncontainerized Job Submission
---------------------------------------------

.. note::

    Due to the nature of scientific workloads that Slurm Clusters are targetted for, SkyShift's initial Slurm support enables submitting jobs to uncontainerized Slurm Clusters. This initial support aims to maximize the performance of Slurm Cluster's compute resources, providing an option for workloads that require direct access to hardware for optimal efficiency. *(See roadmap information below for future support of containerized Slurm Clusters.)*

Looking Ahead: Supporting Container Management Utilities
----------------------------------------

SkyShift is committed to supporting a diverse array of container management tools adopted across different actively managed Slurm Clusters, enabling you to choose the 
one that best fits your project's needs, and will aim to automatically identify the most suitable tool available on the Cluster to streamline the deployment process.

The container manager utilities that are on the feature roadmap are:

- `ContainerD <https://containerd.io/>`_ - A lightweight container runtime that's easy to deploy and manage.

- `Singularity <https://sylabs.io/singularity/>`_ - Designed for high-performance computing, Singularity brings containerization and reproducibility to scientific and analytical computing.

- `PodmanHPC (NERSC) <https://github.com/NERSC/podman-hpc>`_ - An adaptation of Podman tailored for the high-performance computing environment at NERSC.

- `Podman <https://podman.io/>`_ - An open-source, daemon-less container engine, designed for developing, managing, and running OCI Containers on your Linux System.

- `Docker <https://www.docker.com/>`_ - The de facto standard in container technology, known for its ease of use and comprehensive feature set.

