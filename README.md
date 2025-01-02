# ✈️ SkyShift
<h3 align="left">
    Run Any Workload on Any Compute 🌐
</h3>

[![Up to Date](https://github.com/ikatyang/emoji-cheat-sheet/workflows/Up%20to%20Date/badge.svg)](https://github.com/ikatyang/emoji-cheat-sheet/actions?query=workflow%3A%22Up+to+Date%22)
<a href="https://sky-shift.github.io/">
<img alt="Documentation" src="https://img.shields.io/badge/🗏-Docs-orange">
</a>

----
📰 **News** 📰


----
## ⚡Quick Install

Install with pip:
```bash
# Clone SkyShift to local repo
git clone https://github.com/sky-shift/skyshift.git && cd skyshift
# Install SkyShift dependencies for clients.
pip install -e .
# (Optional) SkyShift dependencies for admins.
pip install -e .[server]
```

## 🤔 What is SkyShift?

**SkyShift** is a unified framework for running workloads anywhere—from on-premises compute to edge devices and cloud instances. 

SkyShift **abstracts away many clusters into one contiuuum of compute**, achieving [the Sky](https://arxiv.org/abs/2205.07147):
- Unify Kubernetes, Slurm, and Ray clusters + any cloud instance into one singular cluster.
- Automatically manages job and services.
- Transparently handles networking and communication across clusters.

SkyShift **simplifies workload and compute management**:
- Supports one unified job/service API across clusters.
- Automatically autoscale cloud clusters and manually add/remove existing clusters.

## 🚀 Launch SkyShift 

SkyShift requires at least one cluster to run. This example will use [Kind](https://kind.sigs.k8s.io/), which provisions local Kubernetes (K8) clusters on your local laptop:

```bash
# Launch two K8 clusters.
for i in {1..2};
do
kind create cluster --name cluster$i
done
```

Once the K8 clusters are provisioned, launch SkyShift:

```bash
# In skyshift root path
./launch_skyshift.sh
```

Check SkyShift's status:
```bash
> skyctl get clusters
NAME               MANAGER    RESOURCES                          STATUS
cluster1             k8       cpus: 1.83/2.0                     READY
                              memory: 6035.6/7954.6 MiB
cluster2             k8       cpus: 1.83/2.0                     READY
                              memory: 6035.6/7954.6 MiB
```

Congrats! SkyShift is now ready to submit jobs with its [simplified interface](https://sky-shift.github.io/getting_started/cli_docs.html#skyshift-job). Provided below is an example YAML for a simple Nginx deployment:

```yaml
kind: Job

metadata:
  name: example-job
  labels:
    app: nginx

spec:
  replicas: 2
  image: nginx:1.14.2
  resources:
    cpus: 1
    memory: 128
  ports:
    - 80
  # Always restart a job's tasks, regardless of exit code.
  restartPolicy: Always
```

To create a SkyShift job, run the following command:

```bash
skyctl apply -f [PATH_TO_JOB].yaml
```

Since one cluster does not have sufficient resources, SkyShift automatically schedules and launches the job across two clusters:

```
> skyctl get jobs
NAME          CLUSTER    REPLICAS    RESOURCES               NAMESPACE    STATUS
example-job   cluster1   2/2         cpus: 1                 default      RUNNING
              cluster2               memory: 128.0 MiB

> skyctl get clusters
NAME               MANAGER    RESOURCES                          STATUS
cluster1             k8       cpus: 0.83/2.0                     READY
                              memory: 5907.6/7954.6 MiB
cluster2             k8       cpus: 0.83/2.0                     READY
                              memory: 5907.6/7954.6 MiB
```

Finally, clean up SkyShift and the two K8 clusters:
```
# Kill SkyShift service
./launch_skyshift.sh --kill
# Terminate Kind clusters
for i in {1..2};
do
kind delete cluster --name cluster$i
done
```

Refer to [Quickstart](https://sky-shift.github.io/quickstart/quickstart.html) to get started with SkyShift.

## 📖 Documentation

The above tutorial describes a small subset of features SkyShift supports. Refer to the documentation for a more complete set. For example, SkyShift supports:
- [Slurm](https://sky-shift.github.io/slurm_support/overview.html)  and [Ray](https://sky-shift.github.io/ray/overview.html) clusters.
- Automatic management of [services](https://sky-shift.github.io/cli/services.html) via [ClusterLink](https://clusterlink.net/).
- Fine-grained [Role-based Access Control (RBAC)](https://sky-shift.github.io/cli/roles.html) for [regular users](https://sky-shift.github.io/authentication/authentication.html).
- [Advanced scheduling](https://sky-shift.github.io/architecture/scheduler.html), including custom priorities, preferences, and filters.
- Advanced examples, incl. but not limited to LLM serving with [vLLM](https://sky-shift.github.io/examples/vllm.html), large-scale data processing with [SparkSQL](https://github.com/sky-shift/skyshift/tree/main/examples/tpcds), and general [microservices](https://sky-shift.github.io/examples/bookinfo.html). 

## 🙋 Contributions

As an open-source project, we gladly welcome all contributions, whether it be a new feature, better documentation, or simple bug fixes. For more information, see [here](https://github.com/sky-shift/skyshift/blob/main/CONTRIBUTING.md).
