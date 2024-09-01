# Tutorial - Running Spark with SkyShift

### 1. Creating a config file:

Spark jobs can be run via both standalone command and a config file which can be applied.
Since there can be multiple configs involved, we will go through creating a config file and 
applying it via SkyShift.

Refer to `spark/pyspark_example.yaml`

To get started, a Spark docker image is required which bundles the necessary dependencies
along with the application code.

### 2. Running Pi calculation via Spark

For this tutorial, we use the official Apache PySpark Image `apache/spark-py:latest`
This carries all the necessary Spark dependencies along with example applications.

The image can be configured in the Yaml in the following manner:

```
kind: Job    # This will be submitted as a SkyShift Job
metadata:
  name: pyspark # Name of the job, this can be referenced to view status, logs, deletion etc.
  namespace: default # We use a default namespace, this can be customized to submit in a specific namespace.
  labels: {} # Default
spec:
  image: apache/spark-py:latest # Using official Spark-Py image, can be replaced to run custom applications.
  volumes: {} # Default
  envs: {} # Default
  resources:
    cpus: 1.0 # Configure the CPU Requirements for SkyShift
    gpus: 0 # GPU Requirements
    memory: 0.0 # Default
  run: "/opt/entrypoint.sh driver /opt/spark/examples/src/main/python/pi.py" 
  # A simple pi calculator running in Driver mode. The entrypoint in the image will setup
  # classpath and other environment variables, and perform a spark-submit in driver mode.
  replicas: 1 # Default
  restart_policy: Never # Default
```

### 3. Launching the Job

Once configured, the config can be applied via SkyShift, which will submit this in the cluster pod.
This can be done using: `skyctl apply -f pyspark_example.yaml`

```
  ⠙ Applying configuration
  Created job pyspark.
  ✔ Applying configuration completed successfully.
```

Congrats, you have submitted a Spark job on SkyShift, let's view the jobs to monitor it's execution.
`skyctl get jobs`

```
  ⠙ Fetching jobs
  NAME     CLUSTER    REPLICAS    RESOURCES    NAMESPACE    STATUS    AGE
  pyspark  minikube   1/1         cpus: 1.0    default      RUNNING   9s
  ✔ Fetching jobs completed successfully.
```

The logs can be viewed by SkyShift logs and viewing the pod logs, let's take a look at the logs.
`kubectl logs <pod>`

```
24/09/01 05:28:56 INFO TaskSchedulerImpl: Removed TaskSet 0.0, whose tasks have all completed, from pool 
24/09/01 05:28:56 INFO DAGScheduler: ResultStage 0 (reduce at /opt/spark/examples/src/main/python/pi.py:42) finished in 2.067 s
24/09/01 05:28:56 INFO DAGScheduler: Job 0 is finished. Cancelling potential speculative or zombie tasks for this job
24/09/01 05:28:56 INFO TaskSchedulerImpl: Killing all running tasks in stage 0: Stage finished
24/09/01 05:28:56 INFO DAGScheduler: Job 0 finished: reduce at /opt/spark/examples/src/main/python/pi.py:42, took 2.204323 s
Pi is roughly 3.139120
24/09/01 05:28:56 INFO SparkContext: SparkContext is stopping with exitCode 0.
24/09/01 05:28:56 INFO SparkUI: Stopped Spark web UI at http://pyspark-a29f6434-0:4040
```

We can see `Pi is roughly 3.139120` indicating a successful execution, let's take a look at status again to confirm this.
`skyctl get jobs`

```
  ⠙ Fetching jobs
  NAME     CLUSTER    REPLICAS    RESOURCES    NAMESPACE    STATUS     AGE
  pyspark  minikube   1/1         cpus: 1.0    default      COMPLETED  5m
  ✔ Fetching jobs completed successfully.
```

Skyctl confirms that the job was completed successfully, we can now remove this via `skyctl delete job  pyspark`.
The environment setup and running the same example is also packed with `setup_and_run_spark.sh` if you prefer
to run this as a standalone script.
