# Slurm integration for skyflow
```
API integration from skyctl to skyflow api_server to slurmRESTful API.
```
https://slurm.schedmd.com/configurator.html

# slurmrestd
```
Example slurmrestd setup

Set environmental for binded unix socket
export SLURMRESTD=/var/lib/slurm-llnl/slurmrestd.socket

Set environmental variable for OpenAPI version
export SLURMOPENAPI="v0.0.36"

Start slurmrestd
slurmrestd -s $SLURMOPENAPI unix:$SLURMRESTD -a rest_auth/local -vvv

```

slurm_api.py
```
    get_status()
    get node status, slurm configuration settings

```

Slurm commands
```
    sbatch
    srun
    #Get node statuses
    sinfo -all
    #change node state
    scontrol update NodeName={nodename} state=RESUME
```

# Dealing with nodes
```
    Check allocatable resources
    scontrol show node <node_name>

    sinfo --Node --Format="%10N %10c %10C %10D"
    curl --unix-socket "${SLURMRESTD}" 'http://localhost:8080/slurm/v0.0.38/node/{nodename}'

```
Exposing unix port to inet
```
socat -v tcp-l:6666,reuseaddr,fork unix:/var/lib/slurm-llnl/slurmrestd.socket
```
# GPU Support
    Nvidia
    nvidia-smi
    Product Name -> gres

    AMD
    rocm-smi

#

# TODO

Look into slurm exit code

KubernetesManager add resource getting methods

total resources, allocatable resources
dumb method:
    get node total resources
    loop through all queued jobs
    subtract
rest api, get allocatable resources
scontrol show nodes

services
    tool to update service
    create and delete service

manager.py, import and override for slurm

Slurm watchdog, poll asynchrnoously every X time


# Docker
```
docker build --tag {} {dir}
docker run --rm {tag}
docker inspect {tag}

docker pull registry.example.com/your_image:tag

# Run the Docker container
docker run --gpus all \
           --rm \
           -v /path/to/host/data:/path/in/container \
           registry.example.com/your_image:tag \
           /app/your_executable
```
