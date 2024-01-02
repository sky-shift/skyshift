# Sky Manager - Sky as a Service

Sky Manager is an implementation of a centralized broker. This is currently a prototype (~2k LOC) and currently supports scheduling across multiple clusters.

## Installing Sky Manager

(Optional) Create new conda enviornment

```
conda create -n sky python=3.9
```

Install dependencies, Sky Manager packages, and setup cli

```
bash api_server/install_etcd.sh
python setup.py install
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

Launch the API server on a separate tmux or screen window:

```
cd sky-manager/sky_manager/api_server
python launch_server.py
```

### 3. Launch Controller Manager.

Launch the Controller Manager (which manages Skylet controller + Scheduler controller) on a separate tmux or screen window:

```
cd sky-manager/sky_manager
python launch_sky_manager.py
```

### 4. Add Kubernetes Clusters on Sky Manager

Add the Kubernetes clusters to Sky Manager:

```
skyctl create-cluster --name [CLUSTER_NAME] --manager_type k8
```

In accordance with the example in Step 1:
```
skyctl create-cluster --name mluo-onprem --manager_type k8
skyctl create-cluster --name mluo-onprem --manager_type k8
```

Check the status of the clusters using `skym list-clusters`. The output should look like:
```
Name         Manager     Resources                          Status
mluo-cloud   k8          cpu: 3.86/4.0                      READY
                         gpu: 0/0
                         memory: 12071.359375/15909.359375
mluo-onprem  k8          cpu: 3.86/4.0                      READY
                         gpu: 0/0
                         memory: 12071.359375/15909.359375
```

### 5. Congrats. Submit jobs!

Jobs an be submitted with `skym create-jobs`:

```
skyctl create job --run 'echo hi; sleep 300; echo bye' [name]
```

Check the status of the jobs using `skyctl get jobs`. The output should look like:

```
Name    Cluster      Resources    Status
hello   mluo-onprem  cpu: 1       COMPLETED
hello1  mluo-cloud   cpu: 2       COMPLETED
hello2  mluo-onprem  cpu: 1       COMPLETED
hello3  mluo-onprem  cpu: 2       COMPLETED
hello4  mluo-cloud   cpu: 1       COMPLETED
hello5  mluo-onprem  cpu: 1       COMPLETED
```


