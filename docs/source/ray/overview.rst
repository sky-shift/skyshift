Overview
========

SkyShift: Revolutionizing Job Management on Ray Clusters
--------------------------------------------------------

SkyShift stands at the forefront of job management, seamlessly integrating with Ray Clusters to 
offer an intuitive, powerful interface for managing computational tasks. Ray, the renowned 
open-source, distributed computing framework, caters to a wide range of applications. From machine learning to data processing, 
Ray's versatility shines in parallelizing tasks, orchestrating job execution, and efficiently 
managing resources. Discover the expansive capabilities of 
Ray `here <https://docs.ray.io/en/latest/>`_.

Empowering Researchers and Engineers
-------------------------------------

SkyShift's integration with Ray opens new horizons for researchers and engineers, allowing for 
effortless submission of jobs to distributed computing environments. This level 
of flexibility ensures that your computational research and engineering tasks are executed 
efficiently, leveraging the best available resources.

Containerization: A Core Principle
-----------------------------------

In the current landscape, SkyShift mandates that all jobs submitted to Ray Clusters be 
containerized. This approach guarantees compatibility and optimizes the execution across different 
environments, ensuring that your jobs are run in an isolated, controlled, and reproducible manner. 
SkyShift automatically identifies the most suitable container management tool available on the Ray 
Cluster from its supported list, streamlining the deployment process.

Supported Container Management Utilities
----------------------------------------

SkyShift proudly supports a diverse array of container management tools, enabling you to choose the 
one that best fits your project's needs:

- `ContainerD <https://containerd.io/>`_ - A lightweight container runtime that's easy to deploy and manage.

- `Singularity <https://sylabs.io/singularity/>`_ - Designed for high-performance computing, Singularity brings containerization and reproducibility to scientific and analytical computing.

- `Podman <https://podman.io/>`_ - An open-source, daemon-less container engine, designed for developing, managing, and running OCI Containers on your Linux System.

- `Docker <https://www.docker.com/>`_ - The de facto standard in container technology, known for its ease of use and comprehensive feature set.

Looking Ahead: Uncontainerized Job Submission
---------------------------------------------

In anticipation of future enhancements, SkyShift is developing the capability to submit jobs 
uncontainerized. This innovation aims to maximize the performance of Ray Cluster's compute 
resources, providing an option for workloads that require direct access to hardware for optimal 
efficiency.

SkyShift is committed to expanding the frontiers of computational job management, making it more 
accessible, efficient, and flexible for users across various disciplines and industries. Stay tuned 
for more advancements that will continue to elevate your computational research and engineering 
endeavors.