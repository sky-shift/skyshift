# Roadmap

This documents includes planned features for Skyshift in 2024, and early 2025. However, this roadmap is not comprehensive (feel free to propose new features/directions by opening a Git issue, discussion or PR!). 


## Observability and Monitoring

### CLI
- [x] Aggregate resource summarization.
- [x] List jobs.
- [x] General support for job inspection via exec.

### Graphical Dashboard
- [ ] UI to view each cluster and the aggregate available/unavailable resources.
- [ ] Monitor status of jobs and services submitted through Skyshift.

### Data Collection and Export
- [ ] Accumulate usage statistics.
- [ ] Track jobs over time.
- [ ] Track SkyShift events.
- [ ] Track wait times by resource-group.

### General UI/UX Improvements
- [ ] Clean transparent install, start, stop, and uninstall (https://github.com/sky-shift/skyshift/issues/84).

## Testing
- [ ] Tests for Skyshift controllers.
- [ ] Tests for Skyshift compatibility layers (Slurm, Ray).
- [ ] Tests for Skyshift services.
- [ ] Automatic test generation. 
- [ ] GitHub action integration.

## General Features
- [ ] Autoscaler controller - provisions Skypilot clusters when jobs are unschedulable.
- [ ] Finegrained `update` operation on all Skyshift objects (i.e. a user modifies image in Skyshift job).
- [ ] Key and secrets management.

## Cluster Orchestrator Support

### Kubernetes
- [x] Automatic detection of K8 clusters.
- [x] Automatic provisioning option.
- [ ] Support for additional variants of K8, such as Openshift.
- [ ] Support and test automation for enterprise-grade flavors (e.g. OpenShift).

### Slurm
- [ ] Automatic cluster detection. 
- [ ] Automatic provisioning option.
- [ ] Support for container managers (Docker, Podman, Singularity, etc.) on top of Slurm.
- [ ] Service feature/networking layer for Slurm (e.g. using reverse proxy).
- [ ] Storage feature for Slurm.
- [ ] Exec feature for Slurm.

### Ray
- [ ] Automatic cluster detection.
- [ ] Automatic provisioning for Ray cluster (native Skypilot support).

### More Orhcestrators

We invite the community to contribute to Skyshift's compatibility layer, such as one for LSF, Nomad, and Docker Swarm!

## Workload Placement and Scheduling Optimizations
- [ ] Adaptive scheduling optimizations based on tracked workloads.
- [ ] Explicit waiting policies for job launch (how long a job waits until it fails over to another cluster).
- [ ] Leverage usage statistics and/or historic waiting times in placement decisions (see Observability and Monitoring).

## Storage
- [ ] Blob storage support (MinIO, GCS, S3) for K8 and Slurm clusters.
- [ ] Distributed file synchronization across clusters.

## Resilience
- [ ] Automated fail-over option based on workload configuration and resource availability.
 
## SkyShift Examples
- [x] Model serving with vLLM.
- [ ] Model fine-tuning with Llama 3.
- [ ] Workspace Deployment with SkyShift.
- [ ] Multi-cluster Data ETL pipeline (potentially with Spark).
- [ ] Multi-agent Deployment.




