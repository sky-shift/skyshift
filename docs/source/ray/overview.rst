Overview
========

Launch SkyShift on Ray Cluster
------------------------------

SkyShift is a tool that integrates container runtimes with Ray Clusters, providing a straightforward interface for managing computational tasks. Ray is a distributed computing framework that supports a variety of applications, from machine learning to data processing. It excels in parallelizing tasks, orchestrating job execution, and managing resources efficiently. Learn more about Ray's capabilities `here <https://docs.ray.io/en/latest/>`_.

Containerization: A Core Principle
-----------------------------------

SkyShift requires all jobs submitted to Ray Clusters to be containerized. This ensures compatibility and optimizes execution across different environments, allowing jobs to run in an isolated, controlled, and reproducible manner. SkyShift automatically selects the most suitable container management tool available on the Ray Cluster from its supported list, simplifying the deployment process.

Supported Container Management Utilities
----------------------------------------

SkyShift supports Docker as the primary container management tool, known for its ease of use and comprehensive feature set.

Looking Ahead: Uncontainerized Job Submission
---------------------------------------------

SkyShift is working on the ability to submit jobs without containerization. This feature aims to maximize the performance of Ray Cluster's compute resources, providing an option for workloads that need direct access to hardware for optimal efficiency.

In the future, SkyShift plans to support a variety of container management tools, such as ContainerD, Singularity, and Podman, allowing you to choose the one that best fits your project's needs.

SkyShift is dedicated to advancing computational job management, making it more accessible, efficient, and flexible for users across various fields. Stay tuned for more updates that will enhance your computational tasks.