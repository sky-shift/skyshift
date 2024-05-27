# Tutorial - Adding Slurm Clusters to SkyFlow

### 1. Creating a config file

A Slurm config can container multiple clusters. We provide a full example below.
```
# Name of cluster in Skyflow.
my-slurm-cluster:
  # Access config to authenticate into a Slurm node.
  access_config:
    # Users can provide either an SSH password and/or private key.
    password: HelloWorld
    ssh_key: ~/id_rsa
    hostname: 123.456.78.90
    user: alex
  interface: cli
sky-lab-cluster:
  access_config:
    password: HelloWorld
    hostname: llama.millennium.berkeley.edu
    user: michael
  interface: cli
```

Move the config file to `~/.skyconf/slurm_config.yaml`.

### 2. Launch SkyFlow

To launch Skyflow, run in `skyflow/`:

```
./launch_skyflow.sh
```

If Skyflow is already running and the Slurm cluster has not been added yet, attach the cluster:
```
skyctl create cluster my-slurm-cluster --manager slurm 
```

### 3. Run your Skyflow jobs!
```
skyctl create job --cpus 1 --replicas 2 --run "echo hi; sleep 300; echo bye" my-test-job
```