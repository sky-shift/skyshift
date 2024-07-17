# SkyShift - Container Orchestration across the Sky.

SkyShift orchestrates container-based workloads across the Sky. Our goal is to abstract away the notion of many clusters into one super-cluster. It current supports automatic spreading jobs/deployments across clusters and its new feature - a network mesh - that allows for K8 services to natively load balance across pods in local and remote clusters.

## Installing Sky Manager

(Recommended) Create new conda environment

```
conda create -n skyshift python=3.10
conda activate skyshift 
```

Install dependencies, Sky Manager packages, and setup cli
(assuming the repo has been cloned to ./skyshift)
```
cd skyshift
pip install -e .
# Dependencies for SkyShift's API server.
pip install -e .[server]
```

## Steps to run Sky Manager

### 1. Check Kubernetes Clusters

Sky Manager supports Kubernetes clusters that are listed in `kubectl config get-contexts`:

```
>>> kubectl config get-contexts

CURRENT   NAME          CLUSTER                                   AUTHINFO                               
          mluo-cloud    gke_sky-burst_us-central1-c_mluo-cloud    gke_sky-burst_us-central1-c_mluo-cloud    
*         mluo-onprem   gke_sky-burst_us-central1-c_mluo-onprem   gke_sky-burst_us-central1-c_mluo-onprem   
```

### 2. Launch API server.

Launch the API server on a separate tmux or screen window (or nohup). This will automatically install and run ETCD on your machine and launch the API server.

```
# In skyshift/ base folder
python api_server/launch_server.py
```

### 3. Launch Controller Manager.

Launch the Controller Manager (which manages Skylet controller + Scheduler controller) on a separate tmux or screen window:

```
# In skyshift/ base folder
python skyshift/launch_sky_manager.py
```

### 4. Add Kubernetes Clusters on Sky Manager

Check the status of the clusters using `skyctl get clusters`. The output should look like:
```
Name                                    Manager    Resources                          Status
mluo-cloud                              k8         cpus: 1.93/2.0                     READY
                                                   memory: 6035.6796875/7954.6796875
mluo-onprem                             k8         cpus: 1.93/2.0                     READY
                                                   memory: 6035.6796875/7954.6796875
```

If there are no clusters, add more clusters into your `~/.kube/config` file and run:
```
skyctl create cluster --manager k8 [K8_CONTEXT_NAME]
```

### 5. Congrats. Submit jobs!

Jobs an be submitted with `skyctl create jobs`:

```
skyctl create job [name] --replicas [REPLICA_COUNT] --run '[RUN_COMMAND]' --cpus [CPU_COUNT_PER_REPLICA] --labels app nginx
```
All argument can be found in `skyctl create jobs --help`.

Check the status of the jobs using `skyctl get jobs`. The output should look like:

```
Name     Cluster      Replicas    Resources    Namespace    Status
hello    mluo-cloud   1/1         cpus: 1.0    default      RUNNING
hello    mluo-onprem  1/1         cpus: 1.0    default      RUNNING
```

### 6. Create SkyShift services!

Services can be submitted with `skyctl create services`:

```
skyctl create service my-nginx-service --type LoadBalancer --selector app nginx --ports 8008 80 --cluster mluo-onprem
```

This will create a native K8 service on the `mluo-onprem` cluster. If there are replicas, the K8 service will automatically loadbalance across both local and remote pods (in other clusters).
