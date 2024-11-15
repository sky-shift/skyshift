# Tutorial - Running TPCDS with SkyShift

Spark jobs can be run via both standalone command and a config file which can be applied.
Since there can be multiple configs involved, we will go through creating a config file and 
applying it via SkyShift.

Refer to `tpcds/<*.yaml>`

To get started, a Spark docker image is required which bundles the necessary dependencies
along with the application code.

### 1. Setting up the cluster.

To get started, let's setup a simple kind cluster, which will run 2 worker nodes.
Since we need to persist the generated data, we will provide extra mounts to the local file system.

The following config can be used to spin up the kind cluster:

```
# kind-config.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    extraMounts:
      - hostPath: <local_host_path>
        containerPath: /mnt/hostpath/TPCDS
  - role: worker
    extraMounts:
      - hostPath: <local_host_path>
        containerPath: /mnt/hostpath/TPCDS
  - role: worker
    extraMounts:
      - hostPath: <local_host_path>
        containerPath: /mnt/hostpath/TPCDS
```

Let's run this using the following:
`kind create cluster  --config kind-config.yaml`. Once the cluster is up and running,
we can proceed with building a docker image and loading it for the Spark applications.


> ### Tip: Building the Docker Image
>
> For this tutorial, we use the official Apache PySpark Image `apache/spark-py:latest` and add the required dependencies and jars for the benchmarks.  
> We also need to set up and build some external dependencies such as `tpcds-kit` and `spark-sql-perf`.  
> This is beyond the scope of this tutorial, so we have provided a pre-compiled jar for convenience.
> 
> Let's build the image using:
> ```shell
> docker build -t spark-tpcds-with-dsdgen .
> ```
> (From the `tpcds` folder in examples).
>
> ```
> Sending build context to Docker daemon  13.82kB
> Step 1/6 : FROM apache/spark:latest
>  ---> d3ea4aeb842b
> Step 2/6 : USER root
>  ---> Using cache
>  ---> c0215e24177e
> Step 3/6 : RUN apt-get update &&     apt-get install -y gcc make git bison flex
>  ---> Using cache
>  ---> e35dcf756b53
> Step 4/6 : RUN git clone https://github.com/databricks/tpcds-kit.git &&     cd tpcds-kit/tools &&     make OS=LINUX
>  ---> Using cache
>  ---> 8606e1f328a0
> Step 5/6 : COPY TpcdsBenchmark-assembly-0.1.jar /opt/spark/jars/
>  ---> Using cache
>  ---> 52c2da2bd5c3
> Step 6/6 : USER 185
>  ---> Using cache
>  ---> e83b4ffab7ac
> Successfully built e83b4ffab7ac
> Successfully tagged spark-tpcds-with-dsdgen:latest
> ```
> 
> Finally, the image can be loaded into the cluster using:
> ```shell
> kind load docker-image spark-tpcds-with-dsdgen
> ```
> Alternatively, the image can be pushed to a registry and pulled into the nodes later.
> 
### 3. Setting up master/worker deployments

Let's setup the Spark master and workers on which the Spark application will run.

The Spark master will run as a skyctl job which can be run using:
```
kind: Job
metadata:
  name: spark-master-job
  namespace: default
  labels:
    component: spark-master
spec:
  image: spark-tpcds-with-dsdgen
  image_pull_policy: Never
  envs: {}
  resources:
      cpus: 1
      gpus: 0
      memory: 1024
  ports:
    - 7077
    - 8080
  run: "/bin/bash -c 'unset SPARK_MASTER_PORT; unset SPARK_MASTER_HOST; /opt/spark/sbin/start-master.sh && sleep infinity'"
  replicas: 1
  restart_policy: Always
```

This will eventually setup as a kubernetes deployment since we specified restart policy as Always.
Let's apply this using:
`skyctl apply -f <path_to_config>.yaml`

```
⠙ Applying configuration
Created job spark-master-job.
✔ Applying configuration completed successfully.
```

Let's verify that the master job is up and running using `skyctl get jobs`:
```
⠙ Fetching jobs
NAME              CLUSTER    REPLICAS    RESOURCES        NAMESPACE    STATUS    AGE
spark-master-job  kind-kind  1/1         cpus: 1.0        default      RUNNING   43s
                                         memory: 1.00 GB
✔ Fetching jobs completed successfully.
```

We see that the master is up with 1 CPU and 1GB Memory. Similar to this, let's also setup
workers with 2 replicas using `skyctl apply -f <path_to_worker>.yaml`
This completes the setup with 2 replica workers and 1 replica master, let's verify this using:
`skyctl get jobs`

```
⠙ Fetching jobs
NAME              CLUSTER    REPLICAS    RESOURCES        NAMESPACE    STATUS    AGE
spark-master-job  kind-kind  1/1         cpus: 1.0        default      RUNNING   3m
                                         memory: 1.00 GB
spark-worker-job  kind-kind  2/2         cpus: 1.0        default      RUNNING   10s
                                         memory: 1.00 GB
✔ Fetching jobs completed successfully.
```

### 4. Running TPCDS Datagen and Benchmark

To run TPCDS, we must first generate some data. Let's configure a spark application which 
generate 1GB of data with some sample tables on the local disk. This will be later consumed
by the benchmark.

`skyctl apply -f <path to tpcds-benchmark.yaml>` 

This will submit a spark application which will run as a skyshift job and on on a single 
kubernetes pod. Let's run and verify the job using `skyctl get jobs`.

```
⠙ Fetching jobs
NAME                   CLUSTER    REPLICAS    RESOURCES        NAMESPACE    STATUS    AGE
spark-master-job       kind-kind  1/1         cpus: 1.0        default      RUNNING   8m
                                              memory: 1.00 GB
spark-worker-job       kind-kind  2/2         cpus: 1.0        default      RUNNING   5m
                                              memory: 1.00 GB
tpcds-data-generation  kind-kind  1/1         cpus: 1.0        default      RUNNING   5s
                                              memory: 2.00 GB
✔ Fetching jobs completed successfully.

(kubectl get pods):
NAME                                         READY   STATUS    RESTARTS   AGE
cl-controlplane-fcd6f44d6-g4jls              1/1     Running   0          6h21m
cl-dataplane-7985b87db6-jmrvf                1/1     Running   0          6h21m
gwctl                                        1/1     Running   0          6h21m
spark-master-job-b360d754-65fb745bc8-dsmg4   1/1     Running   0          9m25s
spark-worker-job-226b6e17-5c45489458-n9bg7   1/1     Running   0          5m56s
spark-worker-job-226b6e17-5c45489458-nb9pn   1/1     Running   0          5m56s
tpcds-data-generation-5b3ac4f1-0             1/1     Running   0          35s
```

As we can see the job which may take a few minutes depending on the data size.
Let's wait for the job to complete and verify the logs and status using
`skyctl logs tpcds-data-generation`.

The data generation is complete, and spark job exited successfully.
```
13:31:49 INFO TPCDSTables: Generating table web_site in database to /mnt/hostpath/TPCDS/gen_data/web_site with save mode Ignore.
13:31:49 INFO InsertIntoHadoopFsRelationCommand: Skipping insertion into a relation that already exists.
13:31:49 INFO SparkContext: Invoking stop() from shutdown hook
13:31:49 INFO SparkContext: SparkContext is stopping with exitCode 0.
13:31:49 INFO SparkUI: Stopped Spark web UI at http://tpcds-data-generation-5b3ac4f1-0:4040
13:31:49 INFO MapOutputTrackerMasterEndpoint: MapOutputTrackerMasterEndpoint stopped!
13:31:49 INFO MemoryStore: MemoryStore cleared
13:31:49 INFO BlockManager: BlockManager stopped
13:31:49 INFO BlockManagerMaster: BlockManagerMaster stopped
13:31:50 INFO OutputCommitCoordinator$OutputCommitCoordinatorEndpoint: OutputCommitCoordinator stopped!
13:31:50 INFO SparkContext: Successfully stopped SparkContext
13:31:50 INFO ShutdownHookManager: Shutdown hook called
13:31:50 INFO ShutdownHookManager: Deleting directory /tmp/spark-510d51c8-1414-403a-9e4f-b4a999925d90
13:31:50 INFO ShutdownHookManager: Deleting directory /tmp/spark-d4510370-eda9-44a6-9180-9ae35f138b04
```

Once the data gen is complete, we can run the actual spark benchmark on skyshift using:
`skyctl apply -f <path to tpcds-benchmark.yaml>`

We can verify the job submission using `skyctl get jobs`:
```
⠙ Fetching jobs
NAME                   CLUSTER    REPLICAS    RESOURCES        NAMESPACE    STATUS     AGE
spark-master-job       kind-kind  1/1         cpus: 1.0        default      RUNNING    15m
                                              memory: 1.00 GB
spark-worker-job       kind-kind  2/2         cpus: 1.0        default      RUNNING    11m
                                              memory: 1.00 GB
tpcds-data-generation  kind-kind  1/1         cpus: 1.0        default      COMPLETED  6m
                                              memory: 2.00 GB
tpcds-query-runner     kind-kind  1/1         cpus: 0.5        default      RUNNING    16s
                                              memory: 1.00 GB
✔ Fetching jobs completed successfully.
```

The benchmark is in progress and may take a few minutes. We have filtered a single query
for simplicity in the example. Similar to data gen, let's check the logs of the spark 
application using: `skyctl logs tpcds-query-runner`

```
13:35:08 INFO FileFormatWriter: Write Job 28b02f7d-3280-455b-b2f9-9fe2590632b8 committed. Elapsed time: 101 ms.
13:35:08 INFO FileFormatWriter: Finished processing stats for write job 28b02f7d-3280-455b-b2f9-9fe2590632b8.
Showing at most 100 query results now
13:35:11 INFO CodeGenerator: Code generated in 4.448003 ms
Results: sqlContext.read.json("file:/opt/spark/work-dir/performance/timestamp=1728135291212")
13:35:12 INFO SparkContext: Invoking stop() from shutdown hook
13:35:12 INFO SparkContext: SparkContext is stopping with exitCode 0.
13:35:12 INFO SparkUI: Stopped Spark web UI at http://tpcds-query-runner-f57ec606-0:4040
13:35:12 INFO MapOutputTrackerMasterEndpoint: MapOutputTrackerMasterEndpoint stopped!
13:35:12 INFO MemoryStore: MemoryStore cleared
13:35:12 INFO BlockManager: BlockManager stopped
13:35:12 INFO BlockManagerMaster: BlockManagerMaster stopped
13:35:12 INFO OutputCommitCoordinator$OutputCommitCoordinatorEndpoint: OutputCommitCoordinator stopped!
13:35:12 INFO SparkContext: Successfully stopped SparkContext
13:35:12 INFO ShutdownHookManager: Shutdown hook called
13:35:12 INFO ShutdownHookManager: Deleting directory /tmp/spark-23aa6dd0-f8a1-40ba-9013-40eeb2cf6ed5
13:35:12 INFO ShutdownHookManager: Deleting directory /tmp/spark-4a544f17-67d1-41f6-8cc3-77de59e6deaf
```

The benchmark is complete with results located on `/opt/spark/work-dir/performance/`. Congrats you have run spark 
jobs on a multi worker kubernetes env with SkyShift. Let's finally verify the status of all pods and jobs.

```
skyctl get jobs
⠙ Fetching jobs
NAME                   CLUSTER    REPLICAS    RESOURCES        NAMESPACE    STATUS     AGE
spark-master-job       kind-kind  1/1         cpus: 1.0        default      RUNNING    19m
                                              memory: 1.00 GB
spark-worker-job       kind-kind  2/2         cpus: 1.0        default      RUNNING    16m
                                              memory: 1.00 GB
tpcds-data-generation  kind-kind  1/1         cpus: 1.0        default      COMPLETED  10m
                                              memory: 2.00 GB
tpcds-query-runner     kind-kind  1/1         cpus: 0.5        default      COMPLETED  4m
                                              memory: 1.00 GB
✔ Fetching jobs completed successfully.

~ kubectl get pods
NAME                                         READY   STATUS      RESTARTS   AGE
cl-controlplane-fcd6f44d6-g4jls              1/1     Running     0          6h32m
cl-dataplane-7985b87db6-jmrvf                1/1     Running     0          6h32m
gwctl                                        1/1     Running     0          6h32m
spark-master-job-b360d754-65fb745bc8-dsmg4   1/1     Running     0          19m
spark-worker-job-226b6e17-5c45489458-n9bg7   1/1     Running     0          16m
spark-worker-job-226b6e17-5c45489458-nb9pn   1/1     Running     0          16m
tpcds-data-generation-5b3ac4f1-0             0/1     Completed   0          11m
tpcds-query-runner-f57ec606-0                0/1     Completed   0          4m44s
```

This confirms that we were able to run the benchmarks and all pending jobs are now complete.
The master and worker are long running processes which will continue for any future jobs.
Now you can manage your own Spark jobs with SkyShift!