Overview
===================================

SkyFlow is capable of managing jobs on Slurm Clusters. 

This enables great flexibility to submit jobs into supercomputers such as NERSC or compute farms hosted by individual users or institutions.

The default is that all managed jobs submitted to Slurm Clusters **must be containerized**.
SkyFlow will discover which container management tool is both supported by SkyFlow and available on the Slurm Cluster.

The currently available container management utilities supported by SkyFlow are:
- ContainerD
- Singularity
- PodmanHPC (NERSC)
- Podman
- Docker

However, the option to submit uncontainerized to maximize performance of the Slurm Cluster's compute resource is an upcoming option.