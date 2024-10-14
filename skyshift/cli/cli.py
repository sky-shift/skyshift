# pylint: disable=all
"""
SkyShift CLI.
"""
import json
import os
import re
from inspect import signature
from typing import Dict, List, Tuple, Union
from urllib.parse import quote

import click
import yaml
from click_aliases import ClickAliasedGroup
from colorama import Fore, Style
from halo import Halo


def halo_spinner(text):
    """
    Decorator to handle Halo spinner initialization, start, and stop.
    """

    def decorator(func):
        sig = signature(func)
        params = sig.parameters

        def wrapper(*args, **kwargs):
            spinner = Halo(text=f'{text}\n', spinner='dots', color='cyan')
            spinner.start()
            try:
                if 'spinner' in params:
                    result = func(*args, spinner=spinner, **kwargs)
                else:
                    result = func(*args, **kwargs)
                spinner.succeed(f"{text} completed successfully.")
                return result
            except Exception:  # pylint: disable=broad-except
                spinner.fail(f"{text} failed.")
                raise

        return wrapper

    return decorator


@click.group()
def cli():
    """SkyShift CLI."""
    return


@click.group(cls=ClickAliasedGroup)
def create():
    """Create an object."""
    return


@click.group(cls=ClickAliasedGroup)
def get():
    """Get an object."""
    return


@click.group(cls=ClickAliasedGroup)
def delete():
    """Delete an object."""
    return


@click.group(cls=ClickAliasedGroup)
def apply():
    """Create an object from a config file."""
    return


@click.group(cls=ClickAliasedGroup)
def logs():
    """Fetch logs for a job."""
    return


@click.group(cls=ClickAliasedGroup)
def config():
    """Fetch logs for a job."""
    return


cli.add_command(create)
cli.add_command(get)
cli.add_command(delete)
cli.add_command(apply)
cli.add_command(logs)
cli.add_command(config)


def validate_input_string(value: str) -> bool:
    """
    Validates if the given key matches the required pattern including
    an optional domain prefix and is less than 253 characters.
    """
    if value.startswith("kubernetes.io/") or value.startswith("k8s.io/"):
        return False
    pattern = re.compile(
        r'^([a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*/)?[a-z0-9]([-a-z0-9-.]{0,251}[a-z0-9])?$'
        # pylint: disable=line-too-long
    )
    return bool(pattern.fullmatch(value))


def validate_value_string(value: str) -> bool:
    """Validates if the given value matches the required pattern and is less than 63 characters."""
    pattern = re.compile(r'^[a-z0-9]([-a-z0-9-.]{0,61}[a-z0-9])?$')
    return bool(pattern.fullmatch(value))


def validate_labels(labels: List[Tuple[str, str]]) -> bool:
    """Validates list of labels."""
    for key, value in labels:
        if not validate_input_string(key) or not validate_value_string(value):
            click.echo(f"Error: Invalid label: {key}:{value}", err=True)
            return False
    return True


def cluster_exists(name: str) -> bool:
    """Checks if the given cluster exists in the database."""
    from skyshift.cli.cli_utils import \
        get_cli_object  # pylint: disable=import-outside-toplevel
    api_response = get_cli_object(object_type="cluster", name=name)
    return api_response is not None and api_response.metadata.name == name


def validate_image_format(image: str) -> bool:
    """Validates if the given image matches the Docker image format."""
    pattern = re.compile(
        r'^([a-zA-Z0-9.-]+)?(:[a-zA-Z0-9._-]+)?(/[a-zA-Z0-9._/-]+)?(:[a-zA-Z0-9._-]+|@sha256:[a-fA-F0-9]{64})?$'
        # pylint: disable=line-too-long
    )
    return bool(pattern.fullmatch(image))


def validate_resources(resources: Dict[str, float]) -> bool:
    """
    Validates resource specifications.
    """
    from skyshift.templates.resource_template import \
        ResourceEnum  # pylint: disable=import-outside-toplevel
    valid_resource_types = {item.value for item in ResourceEnum}
    return all(key in valid_resource_types and value >= 0
               for key, value in resources.items())


def validate_accelerator(accelerator: Union[str, None]) -> bool:
    """Validates accelerator specification format and checks if it's a valid type."""
    from skyshift.templates.job_template import \
        AcceleratorEnum  # pylint: disable=import-outside-toplevel
    if accelerator is None:
        return True  # No accelerator specified, considered valid

    valid_accelerator_types = {item.value for item in AcceleratorEnum}
    try:
        acc_type, acc_count_str = accelerator.split(":")
        acc_count = int(acc_count_str)  # Convert count to integer
    except ValueError:
        return False  # Conversion to integer failed or split failed, invalid format

    if acc_type not in valid_accelerator_types or acc_count < 0:
        return False  # Invalid accelerator type or negative count

    return True


def validate_restart_policy(policy: str) -> bool:
    """Validates if the given restart policy is supported."""
    from skyshift.templates.job_template import \
        RestartPolicyEnum  # pylint: disable=import-outside-toplevel
    return RestartPolicyEnum.has_value(policy)


# Apply as CLI
@click.command(name="apply")
@click.option("--file",
              "-f",
              required=True,
              help="Path to config file (YAML).")
@halo_spinner("Applying configuration")
def apply_config(file: str, spinner):
    """Converts a config file to a SkyShift object."""
    from skyshift.cli.cli_utils import \
        create_cli_object  # pylint: disable=import-outside-toplevel

    if file is None:
        spinner.fail("File must be specified.")
        raise Exception("File must be specified.")

    absolute_config_path = os.path.abspath(os.path.expanduser(file))
    if not os.path.exists(absolute_config_path):
        spinner.fail(f"File {absolute_config_path} does not exist.")
        raise Exception(f"File {absolute_config_path} does not exist.")

    with open(os.path.expanduser(absolute_config_path), "r") as config_file:
        config_dict = yaml.safe_load(config_file)

    create_cli_object(config_dict)


cli.add_command(apply_config)


# ==============================================================================
# Cluster API as CLI
@create.command(name="cluster",
                aliases=["clusters"],
                help="""

    Create a new cluster and attach to SkyShift. Once attached, the cluster can be
    managd via SkyShift and made available for jobs submitted to SkyShift.
    This supports clusters managed via Kubernetes, Slurm and Ray.

    Cluster creation supports customized provisioning requirements such as
    Nodes, Regions, CPU and Memory requirements. Post creation SkyShift monitors
    the status and makes it available to the user.

    Examples:
        1. **Create a basic cluster with Kuberntes**:
    
           .. code-block:: bash
    
               skyctl create cluster my-cluster --manager=k8 --cpus=4 --memory=16GB --disk_size=100 --num_nodes=3
    
           The above command creates a cluster named `my-cluster` with Kubernetes as the cluster manager.
           The cluster will be provisioned with 3 nodes, each node with 4 virtual CPUs (vCPUs), 16GB of
           memory, and a 100GB OS disk. Additionally configs, host, username and other properties can be
           passed for any custom requirements.
    
        2. **Create a GPU-Accelerated Cluster via Ray**:
    
           .. code-block:: bash
    
               skyctl create cluster gpu-cluster --manager=ray --cpus=8 --memory=64GB --accelerators=V100:2
                --num_nodes=5 --cloud=gcp --region=us-central1 --ports=22,8888 --provision
    
           This command sets up a cluster named `gpu-cluster` managed by Ray. It provisions 5 nodes in
           the cluster. Each node provisioned with 8 vCPUs, 64GB of memory, and 2 NVIDIA V100 GPUs. The
           cloud flag indicates the cluster provisioning on GCP with us-central1 region. Further, it opens
           up ports 22 and 8888 for remote access via SSH or Jupyter notebook.
    
        3. **Cluster with Specific Cloud and Region**:
    
           .. code-block:: bash
    
               skyctl create cluster cloud-cluster --cloud=aws --region=us-west-2 --manager=slurm --cpus=16
                --memory=128GB
    
           This command creates a cluster named `cloud-cluster` on AWS. Slurm will be  used as the cluster
           manager. The cluster will be provisioned in the `us-west-2` region. Each node in this cluster
           will have 16 vCPUs and 128GB of memory.

    """)
@click.argument('name', required=True)
@click.option(
    "--labels",
    "-l",
    type=(str, str),
    multiple=True,
    default=[],
    help="Key-value pairs for cluster labels",
)
@click.option('--manager',
              default='k8',
              show_default=True,
              required=True,
              help='Cluster manager type (e.g. k8, slurm, ray).')
@click.option('--cpus',
              default=None,
              type=str,
              required=False,
              help='Number of vCPUs per node (e.g. 1, 1+).')
@click.option(
    '--memory',
    default=None,
    type=str,
    required=False,
    help='Amount of memory each instance must have in GB. (e.g. 32, 32+).')
@click.option('--disk_size',
              default=None,
              type=int,
              required=False,
              help='OS disk size in GBs')
@click.option('--accelerators',
              default=None,
              type=str,
              required=False,
              help='Type and number of GPU accelerators to use')
@click.option('--ports',
              default=[],
              type=str,
              multiple=True,
              required=False,
              help='Ports to open on the cluster')
@click.option('--num_nodes',
              default=1,
              show_default=True,
              required=False,
              help='Number of SkyPilot nodes to allocate to the cluster')
@click.option(
    '--cloud',
    default=None,
    show_default=True,
    required=False,
)
@click.option(
    '--region',
    default=None,
    show_default=True,
    required=False,
)
@click.option(
    '--ssh_key_path',
    '-k',
    default="",
    show_default=True,
    required=False,
    help=
    'SSH key to use for Ray clusters. It can be a path to a file or the key itself'
)
@click.option('--config',
              '-c',
              '-C',
              default="",
              show_default=True,
              required=False,
              help='Config file for the cluster.')
@click.option('--host',
              '-h',
              '--hostname',
              '-H',
              default="",
              show_default=True,
              required=False,
              help='Host to use for the cluster')
@click.option('--username',
              '-u',
              default="",
              show_default=True,
              required=False,
              help='Username to use for the cluster')
@click.option('--provision',
              is_flag=True,
              help='True if cluster needs to be provisioned on the cloud.')
@halo_spinner("Creating cluster")
def create_cluster(  # pylint: disable=too-many-arguments, too-many-locals
        name: str, labels: List[Tuple[str, str]], manager: str, cpus: str,
        memory: str, disk_size: str, accelerators: str, ports: List[str],
        num_nodes: int, cloud: str, region: str, provision: bool,
        ssh_key_path: str, config: str, host: str, username: str, spinner):  # pylint: disable=redefined-outer-name

    from skyshift import utils  # pylint: disable=import-outside-toplevel
    from skyshift.cli.cli_utils import \
        create_cli_object  # pylint: disable=import-outside-toplevel
    from skyshift.cloud.utils import \
        cloud_cluster_dir  # pylint: disable=import-outside-toplevel
    from skyshift.cluster_lookup.ray_lookup import \
        add_cluster_to_config  # pylint: disable=import-outside-toplevel
    from skyshift.cluster_manager.manager import \
        RAY_MANAGERS  # pylint: disable=import-outside-toplevel
    from skyshift.cluster_manager.manager import \
        SUPPORTED_CLUSTER_MANAGERS  # pylint: disable=import-outside-toplevel
    from skyshift.globals import \
        CPU_NUMBER_VALIDATOR  # pylint: disable=import-outside-toplevel

    if manager not in SUPPORTED_CLUSTER_MANAGERS:
        spinner.fail(f"Unsupported manager_type: {manager}")
        raise click.BadParameter(f"Unsupported manager_type: {manager}")

    name = utils.sanitize_cluster_name(name)
    if not validate_input_string(name):
        spinner.fail("Error: Name format is invalid.")
        raise click.BadParameter("Name format is invalid.")

    if not validate_labels(labels):
        raise click.BadParameter("Invalid label format.")
    if ports:
        ports = list(ports)

    labels_dict = dict(labels)

    # Convert memory and disk_size to MB, default to GB if no unit is provided
    if memory:
        try:
            memory = f"{utils.parse_resource_with_units(memory)}"
        except ValueError as error:
            spinner.fail(str(error))
            raise click.BadParameter(str(error)) from error
    if disk_size:
        try:
            disk_size = f"{utils.parse_resource_with_units(disk_size)}"
        except ValueError as error:
            spinner.fail(str(error))
            raise click.BadParameter(str(error)) from error

    # Validate CPU format
    if cpus:
        # Accepts a string of the form: [+-]number[+-] to simplify the syntax.
        match = re.match(CPU_NUMBER_VALIDATOR, cpus)
        if not match:
            spinner.fail("Error: Invalid CPU format.")
            raise click.BadParameter("Invalid CPU format.")
        # Then construct the valid cpu syntax (e.g. 2+) from the simplified syntax.
        cpus = f"{match.group(2)}+"

    cluster_dictionary = {
        "kind": "Cluster",
        "metadata": {
            "name": name,
            "labels": labels_dict,
        },
        "spec": {
            "manager":
            manager,
            "cloud":
            cloud,
            "region":
            region,
            "cpus":
            cpus,
            "memory":
            memory,
            "disk_size":
            disk_size,
            "accelerators":
            accelerators,
            "ports":
            ports,
            'num_nodes':
            num_nodes,
            'provision':
            provision,
            'access_config': {
                'host': host,
                'username': username,
                'ssh_key_path': ssh_key_path
            },
            'config_path':
            config
            if not provision else f"{cloud_cluster_dir(name)}/kubeconfig",
        },
    }
    create_cli_object(cluster_dictionary)

    # If manager is 'ray', add the cluster configuration to the .skyconf/ray.yaml
    if manager.lower() in RAY_MANAGERS:
        add_cluster_to_config(name, host, username, ssh_key_path,
                              None)  # No password for now


@get.command(name="cluster",
             aliases=["clusters"],
             help="""

    The get cluster command fetches and displays details for one or all clusters
    being managed by SkyShift. This provides the names, managers, statuses, and
    resources (allocated/available) on the cluster.
    You can view all the clusters and their metadata by not providing a specific
    cluster.

    Examples:
        1. **Fetch Details for All Clusters**:
    
           .. code-block:: bash
    
               > skyctl get cluster
               
               ⠙ Fetching clusters
                NAME      MANAGER    LABELS    RESOURCES                  STATUS    AGE
                minikube  k8                   cpus: 15.25/16.0           ERROR     12d
                                               memory: 15.18 GB/15.35 GB
                                               disk: 151.13 GB/151.13 GB
                ✔ Fetching clusters completed successfully.

    
           Running this command without specifying a cluster name will fetch and display details
           for all clusters being managed by SkyShift. This includes each cluster's name, manager type,
           current status, resource allocations and age.
    
        2. **Fetch Details for a Specific Cluster**:
    
           .. code-block:: bash
    
               skyctl get cluster my-cluster
    
           This command fetches and displays details for the cluster named `my-cluster`. The output
           will include the specific details of the cluster, such as the manager type, current status,
           and allocated resources.
    
        3. **Watch for Changes in a Specific Cluster**:
    
           .. code-block:: bash
    
               skyctl get cluster my-cluster --watch
               
               ⠧ Fetching clusterskind='WatchEvent' event_type='UPDATE' object=Cluster(kind='Cluster',
                metadata=ClusterMeta(name='minikube', labels={}, annotations={}, creation_timestamp='2024-08-25T07:52:58',
                resource_version=15163), spec=ClusterSpec(manager='k8', cloud=None, region=None, cpus=None,
                memory=None, disk_size=None, accelerators=None, ports=[], num_nodes=1, provision=False,
                config_path='~/.kube/config', access_config={}), status=ClusterStatus(conditions=
                [{'status': 'INIT', 'transitionTime': '1724572270.4890375'}, {'status': 'READY', 'transitionTime': 
                '1724572378.7774274'}, {'status': 'ERROR', 'transitionTime': '1725679618.1222773'}], status='ERROR',
                allocatable_capacity={'minikube': {'cpus': 15.250000000000002, 'memory': 15543.71484375,
                'disk': 154755.10546875, 'gpus': 0.0}}, capacity={'minikube': {'cpus': 16.0, 'memory': 15713.71484375,
                'disk': 154755.10546875, 'gpus': 0.0}}, network_enabled=False, accelerator_types={}))

    
           By adding the `--watch` flag, this command continuously monitors `my-cluster` for any
           changes. It will provide real-time updates on the cluster's status, resources, and other
           relevant details as they change.

    """)
@click.argument("name", required=False, default=None)
@click.option("--watch",
              "-w",
              default=False,
              is_flag=True,
              help="Performs a watch.")
@halo_spinner("Fetching clusters")
def get_clusters(name: str, watch: bool):

    from skyshift.cli.cli_utils import (  # pylint: disable=import-outside-toplevel
        get_cli_object, print_table)

    api_response = get_cli_object(object_type="cluster",
                                  name=name,
                                  watch=watch)
    print_table('cluster', api_response)


@delete.command(name="cluster",
                aliases=["clusters"],
                help="""

    The ``delete cluster`` command removes a cluster from SkyShift. For a cluster
    being managed by SkyShift, this command simply detaches the cluster. If the
    cluster was provided using SkyShift, this command also removes the cluster from
    the cloud provider.

    Examples:
        **Delete a Cluster Managed by SkyShift**:
    
        .. code-block:: bash
    
            skyctl delete cluster my-cluster
    
        This command deletes the cluster named `my-cluster` from SkyShift. If the cluster
        was only managed (but not provisioned) by SkyShift, it will simply be detached
        from SkyShift's management. If it was provisioned by SkyShift, the cluster will
        be deleted from the cloud provider as well.

    """)
@click.argument("name", required=True)
@halo_spinner("Deleting cluster")
def delete_cluster(name: str):

    from skyshift.cli.cli_utils import \
        delete_cli_object  # pylint: disable=import-outside-toplevel

    delete_cli_object(object_type="cluster", name=name)


# ==============================================================================
# Job API as CLI
@create.command(name="job",
                aliases=["jobs"],
                help="""

    The create job command allows submission of a new job to SkyShift. You can
    also customize the specific job requirements such as Replicas, Memory, CPU
    and more. SkyShift matches the requirements with the available resources to
    best run the job. See more in`scheduling`.

    Examples:
        1. **Create a Basic Job**:
    
           .. code-block:: bash
    
               skyctl create job basic-job --cpus=2 --memory=1024 --run="python script.py"
    
           This command creates a job named `basic-job` with 2 CPUs and 1024 MB of memory
           per task. The job runs the command `python script.py` inside the container.
    
        2. **Create a GPU-Accelerated Job**:
    
           .. code-block:: bash
    
               skyctl create job gpu-job --gpus=1 --accelerators=V100:1 --run="python train.py" --replicas=4
    
           This command creates a job named `gpu-job` that uses 1 GPU per task, specifically
           an NVIDIA V100. The job will run 4 replicas of `python train.py`, which is useful
           for parallel training jobs.
    
        3. **Create a Job with Custom Docker Image and Environment Variables**:
    
           .. code-block:: bash
    
               skyctl create job custom-job --image=tensorflow/tensorflow:latest-gpu --envs=MY_VAR=value --run="bash start.sh"
    
           This command creates a job named `custom-job` using a specific Docker image
           (`tensorflow/tensorflow:latest-gpu`). It also sets the environment variable
           `MY_VAR` to `value` inside the container and runs `bash start.sh` as the
           job command.
            
        3. **Create a Long-Running Job with Specific Restart Policy**:

           .. code-block:: bash
        
               skyctl create job long-running-job --cpus=4 --memory=2048 --run="python server.py" --restart_policy=Always

           This creates a job named `long-running-job` with 4 CPUs and 2048 MB of memory per task. The job runs the
           command `python server.py` inside the container. The restart policy is set to `Always`, meaning that the
           job will be automatically restarted if it fails, which is ideal for long-running jobs like web servers.

        4. **Create a Batch Job with No Restart**:
        
           .. code-block:: bash
        
               skyctl create job batch-job --cpus=2 --memory=1024 --run="python process_data.py" --restart_policy=Never
        
           This creates a job named `batch-job` with 2 CPUs and 1024 MB of memory per task. The job runs the command 
           python process_data.py` inside the container. The restart policy is set to `Never`, which means the job
           will not be restarted if it fails, making it suitable for batch jobs that should run once and exit.

    """)
@click.argument("name", required=True)
@click.option(
    "--namespace",
    type=str,
    default="default",
    show_default=True,
    help="Namespace corresponding to job's location.",
)
@click.option(
    "--labels",
    "-l",
    type=(str, str),
    multiple=True,
    default=[],
    help="Key-value pairs for job labels",
)
@click.option(
    "--image",
    type=str,
    default="ubuntu:latest",
    show_default=True,
    help="Image to run the job in (any docker registry image).",
)
@click.option(
    "--envs",
    "-e",
    type=(str, str),
    multiple=True,
    default=[],
    help="Pass in environment variables to the job.",
)
@click.option("--cpus", type=float, default=1, help="Number of CPUs per task.")
@click.option(
    "--gpus",
    type=int,
    default=0,
    show_default=True,
    help=
    "Number of GPUs per task. Note that these GPUs can be any type of GPU.",
)
@click.option(
    "--accelerators",
    "-a",
    type=str,
    default=None,
    show_default=True,
    help="Type of accelerator resource to use (e.g. T4:1, V100:2)",
)
@click.option("--memory",
              type=float,
              default=0,
              show_default=True,
              help="Total memory (RAM) per task in MB.")
@click.option("--run",
              type=str,
              default="",
              show_default=True,
              help="Run command for the job.")
@click.option("--replicas",
              type=int,
              default=1,
              show_default=True,
              help="Number of replicas to run job.")
@click.option("--restart_policy",
              type=str,
              default="Always",
              show_default=True,
              help="Restart policy for job tasks.")
@click.option("--volumes",
              "-v",
              type=(str, str),
              multiple=True,
              default=[],
              help="Volume mounts for the job.")
@halo_spinner("Creating job")
def create_job(
    name,
    namespace,
    labels,
    image,
    envs,
    cpus,
    gpus,
    accelerators,
    memory,
    run,
    replicas,
    restart_policy,
    spinner,
    volumes,
):  # pylint: disable=too-many-arguments, too-many-locals

    from skyshift import utils  # pylint: disable=import-outside-toplevel
    from skyshift.cli.cli_utils import \
        create_cli_object  # pylint: disable=import-outside-toplevel
    from skyshift.templates.resource_template import \
        ResourceEnum  # pylint: disable=import-outside-toplevel

    # Validate inputs

    if not validate_input_string(name):
        spinner.fail("Invalid name format.")
        raise click.BadParameter("Invalid name format.")

    if not validate_input_string(namespace):
        spinner.fail("Invalid namespace format.")
        raise click.BadParameter("Invalid namespace format.")

    if not validate_labels(labels):
        spinner.fail("Invalid label selector format.")
        raise click.BadParameter("Invalid label selector format.")

    if not validate_image_format(image):
        spinner.fail("Invalid image format.")
        raise click.BadParameter("Invalid image format.")

    if not validate_restart_policy(restart_policy):
        spinner.fail("Invalid restart policy.")
        raise click.BadParameter("Invalid restart policy.")

    resource_dict = {
        ResourceEnum.CPU.value: cpus,
        ResourceEnum.GPU.value: gpus,
        ResourceEnum.MEMORY.value: memory
    }
    if not validate_resources(resource_dict):
        spinner.fail("Invalid resource format.")
        raise click.BadParameter("Invalid resource format.")

    if not validate_accelerator(accelerators):
        spinner.fail("Invalid accelerator format.")
        raise click.BadParameter("Invalid accelerator format.")

    labels = dict(labels)
    envs = dict(envs)

    # Convert memory to MB, default to MB if no unit is provided
    if memory:
        try:
            memory = f"{utils.parse_resource_with_units(memory, 'MB')}"
        except ValueError as error:
            spinner.fail(str(error))
            raise click.BadParameter(str(error)) from error

    job_dictionary = {
        "kind": "Job",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": labels,
        },
        "spec": {
            "image": image,
            "volumes": {bucket: {'container_dir': container_dir} \
                         for bucket, container_dir in volumes},
            "envs": envs,
            "resources": resource_dict,
            "run": run,
            "replicas": replicas,
            "restart_policy": restart_policy,
        },
    }
    create_cli_object(job_dictionary)


@get.command(name="job",
             aliases=["jobs"],
             help="""

    The get job command fetches and displays any job which was submitted
    to SkyShift. This provides the metadata associated for the running job.
    Similar to get clusters, this allows continuously watching for any changes.

    Examples:
        1. **Fetch Details for All Jobs in a Namespace**:
    
           .. code-block:: bash
    
               skyctl get job --namespace=default
    
           This command fetches and displays details for all jobs within the `default` namespace.
           It will include metadata such as the job name, status, and associated resources.
    
        2. **Fetch Details for a Specific Job**:
    
           .. code-block:: bash
    
               skyctl get job my-job --namespace=default
    
           This command fetches and displays details for the job named `my-job` in the `default` namespace.
           The output will include specific details of the job, such as its current status, start time,
           and resource usage.
    
        3. **Watch a Specific Job for Changes**:
    
           .. code-block:: bash
    
               skyctl get job my-job --namespace=default --watch
    
           By adding the `--watch` flag, this command continuously monitors `my-job` for any changes in its
           status or other metadata. This is useful for tracking the progress of a job in real-time.

    """)
@click.argument("name", default=None, required=False)
@click.option(
    "--namespace",
    type=str,
    default="default",
    show_default=True,
    help="Namespace corresponding to job's location.",
)
@click.option("--watch",
              '-w',
              default=False,
              is_flag=True,
              help="Performs a watch.")
@halo_spinner("Fetching jobs")
def get_job(name: str, namespace: str, watch: bool):

    from skyshift.cli.cli_utils import (  # pylint: disable=import-outside-toplevel
        get_cli_object, print_table)

    api_response = get_cli_object(object_type="job",
                                  name=name,
                                  namespace=namespace,
                                  watch=watch)
    print_table('job', api_response)


@click.command(name="logs",
               help="""

    This command fetches and displays the logs for a specific job within a namespace.
    This can be useful for debugging or monitoring an on-going job.

    :param str name: The name of the job to fetch logs for.
    :param str namespace: The namespace of the job whose logs
     are to be fetched. Default is 'default'.

    Examples:
        1. **Fetch Logs for a Specific Job**:
    
           .. code-block:: bash
    
               skyctl logs my-job --namespace=default
    
           This command retrieves and displays the logs for the job named `my-job` in
           the `default` namespace. The logs will be output directly to the console,
           allowing you to monitor the job's execution or diagnose issues.
    
    """)
@click.argument("name", default=None, required=False)
@click.option(
    "--namespace",
    type=str,
    default="default",
    show_default=True,
    help="Namespace corresponding to job's namespace.",
)
@halo_spinner("Fetching job logs")
def job_logs(name: str, namespace: str):

    from skyshift.cli.cli_utils import \
        fetch_job_logs  # pylint: disable=import-outside-toplevel

    fetch_job_logs(name=name, namespace=namespace)


cli.add_command(job_logs)


@delete.command(name="job",
                aliases=["jobs"],
                help="""

    Deletes a specified job from the given namespace.
    This command permanently removes the job from the specified namespace.
    This terminates and de-allocates any resources provisioned to the job.

    Examples:
        1. **Delete a Job from the Default Namespace**:
    
           .. code-block:: bash
    
               skyctl delete job my-job --namespace=default
    
           This command deletes the job named `my-job` from the `default` namespace.
           The job is terminated, and any associated resources are released.
    
    """)
@click.argument("name", required=True)
@click.option(
    "--namespace",
    type=str,
    default="default",
    show_default=True,
    help="Namespace corresponding to job's location.",
)
@halo_spinner("Deleting job")
def delete_job(name: str, namespace: str):

    from skyshift.cli.cli_utils import \
        delete_cli_object  # pylint: disable=import-outside-toplevel

    delete_cli_object(object_type="job", name=name, namespace=namespace)


# ==============================================================================
# Namespace API as CLI
@create.command(name="namespace",
                aliases=["namespaces"],
                help="""

    The create namespace command creates a new namespace within SkyShift.
    This command initializes a new namespace specified by the 'name' argument.
    You can use this for resource management, security and resource isolation
    within SkyShift.

    Examples:
        **Create a New Namespace**:
    
           .. code-block:: bash
    
               skyctl create namespace dev-environment
    
           This command creates a new namespace named `dev-environment`. SkyShift Namespaces
           can be used to group resources logically and enforce security and resource isolation.
           For example, you might create different namespaces for development, staging,
           and production environments.
    
    """)
@click.argument("name", required=True)
@halo_spinner("Creating namespace")
def create_namespace(name: str, spinner):

    from skyshift.cli.cli_utils import \
        create_cli_object  # pylint: disable=import-outside-toplevel

    # Validate the namespace name
    if not validate_input_string(name):
        spinner.fail("The namespace name is invalid.")
        raise click.BadParameter(f"The namespace name '{name}' is invalid.")

    namespace_dictionary = {
        "kind": "Namespace",
        "metadata": {
            "name": name,
        },
    }
    create_cli_object(namespace_dictionary)


@get.command(name="namespace",
             aliases=["namespaces"],
             help="""

    The ``get namespace`` command allows fetching of details about one or all
    namespaces being managed by SkyShift. This command provides detailed information
    about the specified namespace or all namespaces if no name is provided. If the
    `watch` option is enabled, it will continuously monitor and output updates for
    the namespace(s).

    Examples:
        1. **Fetch Details for All Namespaces**:
    
           .. code-block:: bash
    
               skyctl get namespace
    
           This command fetches and displays details for all namespaces managed by SkyShift.
           It provides an overview of all available namespaces, including their status, name,
           and age.
    
        2. **Fetch Details for a Specific Namespace**:
    
           .. code-block:: bash
    
               skyctl get namespace dev-environment
    
           This command fetches and displays detailed information about the `dev-environment` namespace.
           The output includes metadata such as the namespace's name, status and age.
    
        3. **Watch a Specific Namespace for Changes**:
    
           .. code-block:: bash
    
               skyctl get namespace dev-environment --watch

    """)
@click.argument("name", required=False, default=None)
@click.option("--watch",
              "-w",
              default=False,
              is_flag=True,
              help="Performs a watch.")
@halo_spinner("Fetching namespaces")
def get_namespace(name: str, watch: bool):
    from skyshift.cli.cli_utils import (  # pylint: disable=import-outside-toplevel
        get_cli_object, print_table)

    api_response = get_cli_object(object_type="namespace",
                                  name=name,
                                  watch=watch)
    print_table('namespace', api_response)


@delete.command(name="namespace",
                aliases=["namespaces"],
                help="""

    Deletes a specified namespace from SkyShift. This command permanently
    removes the namespace being managed by SkyShift. Returns an error if
    the namespace does not exist.

    Example:
    **Delete a Namespace**:
    
    .. code-block:: bash
    
        skyctl delete namespace dev-environment
    
    This command deletes the `dev-environment` namespace from SkyShift. Once deleted,
    all resources within this namespace are also removed, and the namespace cannot
    be recovered. This is typically used for cleaning up environments that are no longer needed.

    """)
@click.argument("name", required=True)
@halo_spinner("Deleting namespace")
def delete_namespace(name: str):

    from skyshift.cli.cli_utils import \
        delete_cli_object  # pylint: disable=import-outside-toplevel

    delete_cli_object(object_type="namespace", name=name)


# ==============================================================================
# FilterPolicy API as CLI
@create.command(name="filterPolicy",
                aliases=["filterPolicies", "filterpolicy", "filterpolicies"],
                help="""
                
    The ``create filterPolicy`` command introduces a new filter policy into SkyShift, dictating
    the scheduling eligibility of clusters based on the specified inclusion and exclusion criteria.

    Examples:
        1. **Create a Filter Policy with Specific Label Selectors**:
    
           .. code-block:: bash
    
               skyctl create filterPolicy my-policy -l env production -i clusterA -e clusterB
    
           This command creates a filter policy named `my-policy` in the `default` namespace. The
           policy applies to resources  labeled with `env=production`, includes clusterA and excludes
           clusterB during scheduling.

    
        2. **Create a Filter Policy in a Custom Namespace**:
    
           .. code-block:: bash
    
               skyctl create filterPolicy custom-policy --namespace custom-namespace -i clusterA -i clusterB
    
           This command creates a filter policy named `custom-policy` in the `custom-namespace` namespace.
           The policy includes  both `clusterA` and `clusterB` in the scheduling process.

    """)
@click.argument("name", required=True)
@click.option(
    "--namespace",
    type=str,
    default="default",
    show_default=True,
    help="Namespace corresponding to policy's location.",
)
@click.option(
    "--labelSelector",
    "-l",
    type=(str, str),
    multiple=True,
    default=[],
    help="Key-value pairs for selecting over labels.",
)
@click.option(
    "--includeCluster",
    "-i",
    type=str,
    multiple=True,
    default=[],
    help="Clusters to include in scheduling..",
)
@click.option(
    "--excludeCluster",
    "-e",
    type=str,
    multiple=True,
    default=[],
    help="Clusters to exclude in scheduling..",
)
@halo_spinner("Creating filter policy")
def create_filter_policy(  # pylint: disable=too-many-arguments
        name: str, namespace: str, labelselector: List[Tuple[str, str]],
        includecluster: List[str], excludecluster: List[str], spinner):

    from skyshift.cli.cli_utils import \
        create_cli_object  # pylint: disable=import-outside-toplevel

    # Validate name and namespace
    if not validate_input_string(name) or not validate_input_string(namespace):
        spinner.fail("Name or namespace format is invalid.")
        raise click.BadParameter("Name or namespace format is invalid.")

    # Validate label selectors
    if not validate_labels(labelselector):
        spinner.fail("Label selector format is invalid.")
        raise click.BadParameter("Label selector format is invalid.")

    # Check if any input cluster is also an output cluster and vice versa
    if any(cluster in includecluster for cluster in excludecluster):
        spinner.fail("Clusters cannot be both included and excluded.")
        raise click.BadParameter(
            "Clusters cannot be both included and excluded.")

    # Check if clusters exist
    for cluster_name in set(includecluster + excludecluster):
        if not cluster_exists(cluster_name):
            spinner.fail(f"Cluster '{cluster_name}' does not exist.")
            raise click.BadParameter(
                f"Cluster '{cluster_name}' does not exist.")

    labels = dict(labelselector)
    obj_dictionary = {
        "kind": "FilterPolicy",
        "metadata": {
            "name": name,
            "namespace": namespace,
        },
        "spec": {
            "clusterFilter": {
                "include": includecluster,
                "exclude": excludecluster,
            },
            "labelsSelector": labels,
        },
    }
    create_cli_object(obj_dictionary)


@get.command(name="filterPolicy",
             aliases=["filterPolicies", "filterpolicy", "filterpolicies"],
             help="""

    Fetches details about all or one specific filter policy within a namespace. This
    command provides detailed information about the specified filter policy or all
    policies if no name is provided. If the `watch` option is enabled, it continuously
    monitors and output updates for the policy(s).

    Examples:
        1. **Fetch Details for All Filter Policies**:
    
           .. code-block:: bash
    
               skyctl get filterPolicy --namespace=default
    
           This command fetches and displays details for all filter policies within the
           `default` namespace. It provides an overview of each policy, including its name,
           associated labels, and inclusion/exclusion criteria.
    
        2. **Fetch Details for a Specific Filter Policy**:
    
           .. code-block:: bash
    
               skyctl get filterPolicy my-policy --namespace=default
    
           This command fetches and displays detailed information about the `my-policy` filter
           policy within the `default` namespace. The output includes specific details such as
           the policy's inclusion/exclusion clusters and label selectors.
    
        3. **Watch a Specific Filter Policy for Changes**:
    
           .. code-block:: bash
    
               skyctl get filterPolicy my-policy --namespace=default --watch
    
           By adding the `--watch` flag, this command continuously monitors the `my-policy`
           filter policy for any changes in its details. This is useful for real-time monitoring
           of policy updates, allowing you to track changes as they occur.

    """)
@click.argument("name", required=False, default=None)
@click.option(
    "--namespace",
    type=str,
    default="default",
    show_default=True,
    help="Namespace corresponding to policy's location.",
)
@click.option("--watch", default=False, is_flag=True, help="Performs a watch.")
@halo_spinner("Fetching filter policies")
def get_filter_policy(name: str, namespace: str, watch: bool, spinner):

    from skyshift.cli.cli_utils import (  # pylint: disable=import-outside-toplevel
        get_cli_object, print_table)

    if not validate_input_string(namespace):
        spinner.fail("Name or namespace format is invalid.")
        raise click.BadParameter("Name or namespace format is invalid.")

    api_response = get_cli_object(object_type="filterpolicy",
                                  name=name,
                                  namespace=namespace,
                                  watch=watch)
    print_table('filterpolicy', api_response)


@delete.command(name="filterPolicy",
                aliases=["filterPolicies", "filterpolicy", "filterpolicies"],
                help="""

    Deletes the specified filter policy from the given namespace. Use this command
    to permanently remove the filter policy identified by the given name from the namespace.

    Examples:
        1. **Delete a Filter Policy**:

           .. code-block:: bash
    
               skyctl delete filterPolicy my-policy --namespace=default
    
           This command deletes the `my-policy` filter policy from the `default` namespace.
           Once deleted, the filter policy is permanently removed, and any scheduling rules
           or constraints associated with it are no longer applied.

    """)
@click.argument("name", required=True)
@click.option(
    "--namespace",
    type=str,
    default="default",
    show_default=True,
    help="Namespace corresponding to policy's location.",
)
@halo_spinner("Deleting filter policy")
def delete_filter_policy(name: str, namespace: str, spinner):

    from skyshift.cli.cli_utils import \
        delete_cli_object  # pylint: disable=import-outside-toplevel

    if not validate_input_string(name) or not validate_input_string(namespace):
        spinner.fail("Name or namespace format is invalid.")
        raise click.BadParameter("Name or namespace format is invalid.")

    delete_cli_object(object_type="filterpolicy",
                      name=name,
                      namespace=namespace)


# ==============================================================================
# Link CLI
@create.command(name="link",
                aliases=["links"],
                help="""

    The ``create link`` command creates a new link between two specified clusters,
    enabling them to communicate directly with each other.
    
    Examples:
        1. **Create a Link Between Two Clusters**:
    
           .. code-block:: bash
    
               skyctl create link data-link --source=clusterA --target=clusterB
    
           This command creates a link named `data-link` between `clusterA` (the source cluster)
           and `clusterB` (the target cluster). This allows the two clusters to communicate directly,
           facilitating data exchange or other interactions.

    """)
@click.argument("name", required=True)
@click.option("--source", "-s", required=True, help="Source cluster name")
@click.option("--target", "-t", required=True, help="Target cluster name")
@halo_spinner("Creating link")
def create_link(name: str, source: str, target: str, spinner):
    from skyshift.cli.cli_utils import \
        create_cli_object  # pylint: disable=import-outside-toplevel

    if not validate_input_string(name):
        spinner.fail(f"Link name {name} is invalid.")
        raise click.BadParameter(f"Link name {name} is invalid.")

    if not validate_input_string(source):
        spinner.fail(f"Source cluster {source} is invalid.")
        raise click.BadParameter(f"Source cluster {source} is invalid.")
    if not validate_input_string(target):
        spinner.fail(f"Target cluster {target} is invalid.")
        raise click.BadParameter(f"Target cluster {target} is invalid.")

    if source == target:
        spinner.fail("Source and target clusters cannot be the same.")
        raise click.BadParameter(
            "Source and target clusters cannot be the same.")

    if not cluster_exists(source):
        spinner.fail(f"Source cluster '{source}' does not exist.")
        raise click.BadParameter(f"Source cluster '{source}' does not exist.")
    if not cluster_exists(target):
        spinner.fail(f"Target cluster '{target}' does not exist.")
        raise click.BadParameter(f"Target cluster '{target}' does not exist.")

    obj_dict = {
        "kind": "Link",
        "metadata": {
            "name": name,
        },
        "spec": {
            "source_cluster": source,
            "target_cluster": target,
        },
    }
    create_cli_object(obj_dict)


@get.command(name="link",
             aliases=["links"],
             help="""

    The ``get links`` command fetches the details about one specific link or all links
    between clusters which were created by SkyShift, with an optional watch functionality.

    Examples:    
        1. **Fetch Details for All Links**:
    
           .. code-block:: bash
        
               skyctl get link
        
           This command fetches and displays details for all links created by SkyShift between
           clusters. It provides an overview of each link, including the source and target clusters
           and any relevant metadata.
        
        2. **Fetch Details for a Specific Link**:
    
           .. code-block:: bash
        
               skyctl get link data-link
        
           This command fetches and displays detailed information about the `data-link` link.
           The output includes specific details such as the source and target clusters, creation date,
           and current status of the link.
        
        3. **Watch a Specific Link for Changes**:
    
           .. code-block:: bash
        
               skyctl get link data-link --watch
        
           By adding the `--watch` flag, this command continuously monitors the `data-link` for any
           changes in its details. This is useful for real-time monitoring of link updates, allowing
           you to track changes as they occur.    
          
""")
@click.argument("name", required=False, default=None)
@click.option("--watch",
              "-w",
              default=False,
              is_flag=True,
              help="Performs a watch.")
@halo_spinner("Fetching links")
def get_links(name: str, watch: bool):

    from skyshift.cli.cli_utils import (  # pylint: disable=import-outside-toplevel
        get_cli_object, print_table)

    api_response = get_cli_object(object_type="link", name=name, watch=watch)
    print_table('link', api_response)


@delete.command(name="link",
                aliases=["links"],
                help="""
    
    The delete link command permanently removes the link (identified by the given name)
    from SkyShift.

    Examples:
        1. **Delete a Specific Link**:
        
           .. code-block:: bash
    
               skyctl delete link data-link
    
           This command deletes the `data-link` from SkyShift. Once deleted, the communication link
           between the source and target clusters is permanently removed, and any operations or data
           flows using this link are stopped.
    
    """)
@click.argument("name", required=True)
@halo_spinner("Deleting link")
def delete_link(name: str):

    from skyshift.cli.cli_utils import \
        delete_cli_object  # pylint: disable=import-outside-toplevel

    delete_cli_object(object_type="link", name=name)


# ==============================================================================
# Service API as CLI
@create.command(name="service",
                aliases=["services", "svc"],
                help=""""

    The create service command creates a new service within SkyShift. You can customize this
    for specific namespaces, specific service types, selectors, ports and clusters.

    Examples:
        1. **Create a Basic ClusterIP Service**:
    
           .. code-block:: bash
    
               skyctl create service my-service --namespace=default --service_type=ClusterIP --ports 80 8080
    
           This command creates a service named `my-service` in the `default` namespace. The service
           is of type `ClusterIP` and maps port `80` to `8080` on the target pods. This service
           will be available only within the cluster.
    
        2. **Create a LoadBalancer Service with Selectors**:
    
           .. code-block:: bash
    
               skyctl create service my-service -t LoadBalancer -s app web -p 80 8080
    
           This command creates a `LoadBalancer` service named `my-service`. The service will select
           pods labeled with `app=web` and expose ports `80` and `443`, forwarding them to `8080` and
           `8443` on the target pods, respectively. This service will be accessible from outside the cluster.
    
        3. **Create a Service in a Custom Cluster**:
    
           .. code-block:: bash
    
               skyctl create service custom-service --namespace=default --cluster clusterA --ports 80 8080
    
           This command creates a service named `custom-service` in the `default` namespace, but it will be
           exposed on `clusterA`. The service maps port `80` to `8080` on the target pods and will be
           available within `clusterA`.
       
    """)
@click.argument("name", required=True)
@click.option(
    "--namespace",
    type=str,
    default="default",
    show_default=True,
    help="Namespace corresponding to service's location.",
)
@click.option("--service_type",
              "-t",
              type=str,
              default="NodePort",
              show_default=True,
              help="Type of service.")
@click.option("--selector",
              "-s",
              type=(str, str),
              default=None,
              help="Label selectors.")
@click.option(
    "--ports",
    "-p",
    type=(int, int),
    multiple=True,
    default=[],
    help=
    "Port pairs for service (<port>:<containerPort/targetPort>). Defaults to TCP connection.",
)
@click.option("--cluster",
              "-c",
              type=str,
              default="auto",
              show_default=True,
              help="Cluster to expose service on.")
@halo_spinner("Creating service")
def create_service(
    name: str,
    namespace: str,
    service_type: str,
    selector: List[Tuple[str, str]],
    ports: List[Tuple[int, int]],
    cluster: str,
    spinner,
):  # pylint: disable=too-many-arguments

    from skyshift.cli.cli_utils import \
        create_cli_object  # pylint: disable=import-outside-toplevel
    from skyshift.templates.service_template import \
        ServiceType  # pylint: disable=import-outside-toplevel

    # Validate service name and namespace
    if not validate_input_string(name):
        spinner.fail(f"Service name {name} is invalid.")
        raise click.BadParameter(f"Service name {name} is invalid.")
    if not validate_input_string(namespace):
        spinner.fail(f"Namespace {namespace} is invalid.")
        raise click.BadParameter(f"Namespace {namespace} is invalid.")

    # Validate service type
    if not ServiceType.has_value(service_type):
        spinner.fail(f"Service type '{service_type}' is not supported.")
        raise click.BadParameter(
            f"Service type '{service_type}' is not supported.")

    if isinstance(selector, tuple):
        selector = [selector]
    elif selector is None:
        selector = []

    # Validate selector
    if not all(
            validate_input_string(k) and validate_input_string(v)
            for k, v in selector):
        spinner.fail(f"Selector {selector} is invalid.")
        raise click.BadParameter(f"Selector {selector} is invalid.")

    # Validate ports
    for port, target_port in ports:
        if not 0 < port <= 65535:
            spinner.fail(f"Port {port} is out of valid range.")
            raise click.BadParameter(f"Port {port} is out of valid range.")
        if not 0 < target_port <= 65535:
            spinner.fail(f"Target port {target_port} is out of valid range.")
            raise click.BadParameter(
                f"Target port {target_port} is out of valid range.")

    # @TODO(mluo|acuadron): Implement auto
    # Validate cluster
    if cluster != "auto" and not cluster_exists(cluster):
        spinner.fail(f"Cluster '{cluster}' does not exist.")
        raise click.BadParameter(f"Cluster '{cluster}' does not exist.")

    ports_list = [{
        "port": port,
        "target_port": target_port,
        "protocol": "TCP"
    } for port, target_port in ports]

    selector_dict = {s[0]: s[1] for s in selector} if selector else {}

    service_dictionary = {
        "kind": "Service",
        "metadata": {
            "name": name,
            "namespace": namespace,
        },
        "spec": {
            "type": service_type,
            "selector": selector_dict,
            "ports": ports_list,
            "primary_cluster": cluster,
        },
    }
    create_cli_object(service_dictionary)


@get.command(name="service",
             aliases=["services", "svc"],
             help="""

    The get service command fetches the details about one specific or all services within
    a given namespace, with an optional watch functionality.

    Examples:
        1. **Fetch Details for All Services**:
    
           .. code-block:: bash
    
               skyctl get service --namespace=default
    
           This command fetches and displays details for all services within the `default` namespace.
           It provides an overview of each service, including its type, connected pods, port configurations,
           and other relevant metadata.
    
        2. **Fetch Details for a Specific Service**:
    
           .. code-block:: bash
    
               skyctl get service my-service --namespace=default
    
           This command fetches and displays detailed information about the `my-service` within
           the `default` namespace. The output includes specific details such as the service type,
           connected pods, port configurations, and current status.
    
        3. **Watch a Specific Service for Changes**:
    
           .. code-block:: bash
    
               skyctl get service my-service --namespace=default --watch
    
           By adding the `--watch` flag, this command continuously monitors the `my-service` for
           any changes in its details. This is useful for real-time monitoring of service updates,
           allowing you to track changes as they occur.
       
    """)
@click.argument("name", required=False, default=None)
@click.option(
    "--namespace",
    type=str,
    default="default",
    show_default=True,
    help="Namespace corresponding to service`s location.",
)
@click.option("--watch", default=False, is_flag=True, help="Performs a watch.")
@halo_spinner("Fetching services")
def get_service(name: str, namespace: str, watch: bool):

    from skyshift.cli.cli_utils import (  # pylint: disable=import-outside-toplevel
        get_cli_object, print_table)

    api_response = get_cli_object(object_type="service",
                                  name=name,
                                  namespace=namespace,
                                  watch=watch)
    print_table('service', api_response)


@delete.command(name="service",
                aliases=["services", "svc"],
                help="""

    Deletes a specified service from the given namespace. This command permanently removes
    the service identified by the given name from the specified namespace.

    Examples:
        1. **Delete a Service from the Default Namespace**:
    
           .. code-block:: bash
    
               skyctl delete service my-service --namespace=default
    
           This command deletes the `my-service` from the `default` namespace. Once deleted, the service
           will no longer be available, and any connections or resources associated with it will be terminated.
    
        2. **Delete a Service from a Custom Namespace**:
    
           .. code-block:: bash
    
               skyctl delete service my-service --namespace=production
    
           This command deletes the `my-service` from the `production` namespace. This is useful for cleaning up
           services that are no longer needed in a specific environment or namespace.

    """)
@click.argument("name", required=True)
@click.option(
    "--namespace",
    type=str,
    default="default",
    show_default=True,
    help="Namespace corresponding to service`s location.",
)
@halo_spinner("Deleting service")
def delete_service(name: str, namespace: str):

    from skyshift.cli.cli_utils import \
        delete_cli_object  # pylint: disable=import-outside-toplevel

    delete_cli_object(object_type="service", namespace=namespace, name=name)


# ==============================================================================
# Endpoints API as CLI
@create.command(name="endpoints",
                aliases=["endpoint", "edp", "edps"],
                help="""

    Creates a new set of endpoints within a specified namespace, customizable via user provided
    arguments. This command sets up endpoints, which represent network-accessible points
    associated with a service. These endpoints can be configured to be exposed within a
    cluster and can target specific resources based on label selectors.

    Examples:
        1. **Create Endpoints with Default Settings**:
    
           .. code-block:: bash
    
               skyctl create endpoints my-endpoints --num_endpoints=3
    
           This command creates a set of endpoints named `my-endpoints` in the `default` namespace.
           The endpoints are not exposed to the cluster by default, and they do not have any specific
           label selectors targeting resources.
    
        2. **Create Exposed Endpoints in a Custom Cluster**:
    
           .. code-block:: bash
    
               skyctl create endpoints exposed-endpoints --num_endpoints=5 --exposed --primary_cluster=clusterA
    
           This command creates a set of endpoints named `exposed-endpoints` in the `default` namespace.
           The endpoints are exposed to `clusterA` and can be accessed from other services within that cluster.
           Five endpoints are created in this configuration.
    
        3. **Create Endpoints with Specific Label Selectors**:
    
           .. code-block:: bash
    
               skyctl create endpoints labeled-endpoints --num_endpoints=2 --selector app web
    
           This command creates a set of endpoints named `labeled-endpoints` in the `default` namespace.
           The endpoints are configured to target resources labeled with `app=web`. Two endpoints are created
           in this setup.

""")
@click.argument("name", required=True)
@click.option("--namespace",
              type=str,
              default="default",
              show_default=True,
              help="Namespace for the endpoints.")
@click.option("--num_endpoints", type=int, help="Number of endpoints.")
@click.option("--exposed",
              is_flag=True,
              default=False,
              help="Whether the endpoints are exposed to the cluster.")
@click.option("--primary_cluster",
              type=str,
              default="auto",
              show_default=True,
              help="Primary cluster where the endpoints are exposed.")
@click.option("--selector",
              multiple=True,
              type=(str, str),
              help="Selector key-value pairs.")
@halo_spinner("Creating endpoints")
def create_endpoints(  # pylint: disable=too-many-arguments
        name, namespace, num_endpoints, exposed, primary_cluster, selector,
        spinner):

    from skyshift.cli.cli_utils import \
        create_cli_object  # pylint: disable=import-outside-toplevel

    # Validate inputs
    if not validate_input_string(name):
        spinner.fail(f"Invalid name {name} for endpoints.")
        raise click.BadParameter(f"Invalid name {name} for endpoints.")

    if not validate_input_string(namespace):
        spinner.fail(f"Invalid namespace name: {namespace}.")
        raise click.BadParameter(f"Invalid namespace name: {namespace}.")

    if num_endpoints is not None and num_endpoints < 0:
        spinner.fail("Number of endpoints must be non-negative.")
        raise click.BadParameter("Number of endpoints must be non-negative.")

    if exposed and not primary_cluster:
        spinner.fail("Exposed endpoints must specify a primary cluster.")
        raise click.BadParameter(
            "Exposed endpoints must specify a primary cluster.")

    if primary_cluster != "auto" and not cluster_exists(primary_cluster):
        spinner.fail(f"Invalid primary cluster name: {primary_cluster}")
        raise click.BadParameter(
            f"Invalid primary cluster name: {primary_cluster}")

    selector_dict = dict(selector) if selector else {}

    # Construct the endpoints object
    endpoints_object = {
        "kind": "Endpoints",
        "metadata": {
            "name": name,
            "namespace": namespace,
        },
        "spec": {
            "selector": selector_dict,
            "endpoints": {
                primary_cluster: {
                    "num_endpoints":
                    num_endpoints if num_endpoints is not None else 0,
                    "exposed_to_cluster":
                    exposed
                }
            } if primary_cluster else {},
            "primary_cluster": primary_cluster
        }
    }

    create_cli_object(endpoints_object)


@get.command(name="endpoints",
             aliases=["endpoint", "edp", "edps"],
             help="""

    Use the get endpoints command to fetch the details about one specific or all
    endpoints within a given namespace, with an optional watch functionality.

    Examples:
        1. **Fetch Details for All Endpoints**:
    
           .. code-block:: bash
    
               skyctl get endpoints --namespace=default
    
           This command fetches and displays details for all endpoints within the `default` namespace.
           It provides an overview of each set of endpoints, including their configuration, exposure status,
           and any associated selectors.
    
        2. **Fetch Details for a Specific Set of Endpoints**:
    
           .. code-block:: bash
    
               skyctl get endpoints my-endpoints --namespace=default
    
           This command fetches and displays detailed information about the `my-endpoints` within the `default` namespace.
           The output includes specific details such as the number of endpoints, exposure status, primary cluster,
           and any label selectors applied.
    
        3. **Watch a Specific Set of Endpoints for Changes**:
    
           .. code-block:: bash
    
               skyctl get endpoints my-endpoints --namespace=default --watch
    
           By adding the `--watch` flag, this command continuously monitors the `my-endpoints` for any changes in their details.
           This is useful for real-time monitoring of endpoint updates, allowing you to track changes as they occur.

    """)
@click.argument("name", required=False, default=None)
@click.option(
    "--namespace",
    type=str,
    default="default",
    show_default=True,
    help="Namespace corresponding to service`s location.",
)
@click.option("--watch", default=False, is_flag=True, help="Performs a watch.")
@halo_spinner("Fetching endpoints")
def get_endpoints(name: str, namespace: str, watch: bool):

    from skyshift.cli.cli_utils import (  # pylint: disable=import-outside-toplevel
        get_cli_object, print_table)

    api_response = get_cli_object(object_type="endpoints",
                                  name=name,
                                  namespace=namespace,
                                  watch=watch)
    print_table('endpoints', api_response)


@delete.command(name="endpoints",
                aliases=["endpoint", "edp", "edps"],
                help="""
    Use the delete endpoints command to permanently remove any endpoint being
    managed by SkyShift.

    Examples:
        1. **Delete Endpoints from the Default Namespace**:
    
           .. code-block:: bash
    
               skyctl delete endpoints my-endpoints --namespace=default
    
           This command deletes the `my-endpoints` from the `default` namespace. Once deleted, the endpoints
           will no longer be available, and any resources or services associated with them will be disconnected.
    
        2. **Delete Endpoints from a Custom Namespace**:
    
           .. code-block:: bash
    
               skyctl delete endpoints my-endpoints --namespace=production
    
           This command deletes the `my-endpoints` from the `production` namespace. This is useful for cleaning up
           endpoints that are no longer needed in a specific environment or namespace.
    
    """)
@click.argument("name", required=True)
@click.option(
    "--namespace",
    type=str,
    default="default",
    show_default=True,
    help="Namespace corresponding to service`s location.",
)
@halo_spinner("Deleting endpoints")
def delete_endpoints(name: str, namespace: str):

    from skyshift.cli.cli_utils import \
        delete_cli_object  # pylint: disable=import-outside-toplevel

    delete_cli_object(object_type="endpoints", namespace=namespace, name=name)


# ==============================================================================
# Role API as CLI


@create.command(name="role",
                aliases=["roles"],
                help="""

    Creates a new role with specified permissions and access controls within SkyShift.
    This is highly customizable and allows access management for organizations where
    multiple users, namespaces and resources are involved.

    Examples:
        1. **Create a Role with Specific Actions and Resources**:
    
           .. code-block:: bash
    
               skyctl create role admin-role --action=create --action=delete --resource=pods --resource=services
    
           This command creates a role named `admin-role` that grants permissions to create and delete `pods` and `services`.
           The role can be assigned to users or applied within specific namespaces as needed.
    
        2. **Create a Role with Namespace Restrictions**:
    
           .. code-block:: bash
    
               skyctl create role dev-role --action=view --resource=pods --namespace=dev
    
           This command creates a role named `dev-role` that grants permission to view `pods` only within the `dev` namespace.
           This is useful for limiting the scope of access for users who only need to manage resources in specific environments.
    
        3. **Create a Role and Assign it to Users**:
    
           .. code-block:: bash
    
               skyctl create role team-lead --action=manage --resource=deployments --users=user1 --users=user2
    
           This command creates a role named `team-lead` that grants the ability to manage `deployments`.
           The role is then assigned to `user1` and `user2`, giving them the permissions defined by the role.

    """)
@click.argument("name", required=True)
@click.option("--action",
              "-a",
              type=str,
              multiple=True,
              default=[],
              help="List of actions for the role.")
@click.option("--resource",
              "-r",
              type=str,
              multiple=True,
              default=[],
              help="List of resources for the role.")
@click.option("--namespace",
              "-n",
              type=str,
              multiple=True,
              default=[],
              help="List of namespaces for the role.")
@click.option("--users",
              "-u",
              type=str,
              multiple=True,
              default=[],
              help="List of users for the role.")
@halo_spinner("Creating role")
def create_role(  # pylint: disable=too-many-arguments
        name: str, action: List[str], resource: List[str],
        namespace: List[str], users: List[str], spinner):

    from skyshift.cli.cli_utils import \
        create_cli_object  # pylint: disable=import-outside-toplevel

    if not validate_input_string(name):
        spinner.fail("Name format is invalid.")
        raise click.BadParameter(f"Name format is invalid: {name}")

    # Construct the endpoints object
    role_object = {
        "kind": "Role",
        "metadata": {
            "name": name,
            "namespaces": namespace,
        },
        "rules": [{
            "name": name,
            "resources": resource,
            "actions": action,
        }],
        "users": users,
    }
    create_cli_object(role_object)


@get.command(name="role",
             aliases=["roles"],
             help="""
    The get roles command fetches the roles created in SkyShift and associated permissions/metadata.
    This also allows continuous monitoring to the role if watch is enabled.

    Examples:
        1. **Fetch Details for All Roles**:
    
           .. code-block:: bash
    
               skyctl get role
    
           This command fetches and displays details for all roles created in SkyShift. It provides an overview
           of each role, including its name, associated permissions, resources, namespaces, and users.
    
        2. **Fetch Details for a Specific Role**:
    
           .. code-block:: bash
    
               skyctl get role admin-role
    
           This command fetches and displays detailed information about the `admin-role`. The output includes specific
           details such as the actions permitted by the role, the resources it controls, the namespaces where it applies,
           and the users assigned to it.
    
        3. **Watch a Specific Role for Changes**:
    
           .. code-block:: bash
    
               skyctl get role admin-role --watch
    
           By adding the `--watch` flag, this command continuously monitors the `admin-role` for any changes in its details.
           This is useful for real-time monitoring of role updates, allowing you to track changes as they occur.
    
    """)
@click.argument("name", required=False, default=None)
@click.option("--watch",
              "-w",
              default=False,
              is_flag=True,
              help="Performs a watch.")
@halo_spinner("Fetching roles")
def get_roles(name: str, watch: bool, spinner):

    from skyshift.cli.cli_utils import (  # pylint: disable=import-outside-toplevel
        get_cli_object, print_table)

    if name and not validate_input_string(name):
        spinner.fail("Name format is invalid.")
        raise click.BadParameter(f"Name format is invalid: {name}")

    api_response = get_cli_object(object_type="role", name=name, watch=watch)
    print_table('role', api_response)


@delete.command(name="role",
                aliases=["roles"],
                help="""

    Deletes a specified role from SkyShift. Immediately revokes the role and associated permissions.

    Examples:
        1. **Delete a Specific Role**:
    
           .. code-block:: bash
    
               skyctl delete role admin-role
    
           This command deletes the `admin-role` from SkyShift. Once deleted, all permissions and access
           controls associated with this role are revoked, and the role can no longer be assigned to users.

    """)
@click.argument("name", required=True)
@halo_spinner("Deleting role")
def delete_role(name, spinner):

    from skyshift.cli.cli_utils import \
        delete_cli_object  # pylint: disable=import-outside-toplevel

    if not validate_input_string(name):
        spinner.fail("Name format is invalid.")
        raise click.BadParameter(f"Name format is invalid: {name}")
    delete_cli_object(object_type="role", name=name)


# ==============================================================================
# SkyShift exec


@click.command(name="exec",
               help="""

    Executes a specified command within a container of a resource.

    This function supports executing commands in various modes, including direct execution
    and TTY (interactive) mode.
    It is capable of targeting specific clusters, tasks (pods), and containers, providing
    flexibility in how commands are executed across the infrastructure. It handles both
    single and multiple targets with appropriate checks and balances to ensure the command
    execution context is correctly established.

    Examples:
        1. **Execute a Simple Command in a Resource**:
    
           .. code-block:: bash
    
               skyctl exec my-pod ls /app
    
           This command runs the `ls /app` command in the `my-pod` resource within the default namespace.
           The command lists the contents of the `/app` directory in the specified pod.
    
        2. **Execute a Command in a Specific Container of a Pod**:
    
           .. code-block:: bash
    
               skyctl exec my-pod --containers=my-container ls /app
    
           This command runs the `ls /app` command in the `my-container` within the `my-pod` resource.
           It targets a specific container within the pod, allowing for granular command execution.
    
        3. **Execute a Command with TTY (Interactive) Mode**:
    
           .. code-block:: bash
    
               skyctl exec my-pod --tty bash

           This command opens an interactive `bash` shell in the `my-pod` resource, enabling user interaction
           with the shell through a TTY (interactive) session.

    """)
@click.argument("resource", required=True)
@click.argument("command", nargs=-1, required=True)
@click.option(
    "--namespace",
    type=str,
    default="default",
    show_default=True,
    help="Namespace corresponding to job's location.",
)
@click.option(
    "-t",
    "--tasks",
    multiple=True,
    default=None,
    help=
    "Task name where the command will be executed. This option can be repeated to \
        specify multiple pods.")
@click.option(
    "-cts",
    "--containers",
    multiple=True,
    default=None,
    help=
    "Container name where the command will be executed. This option can be repeated \
        to specify multiple containers.")
@click.option("-q",
              "--quiet",
              is_flag=True,
              default=False,
              help="Only print output from the remote session.")
@click.option("-it",
              "-ti",
              "--tty",
              is_flag=True,
              default=False,
              help="Stdin is a TTY.")
@halo_spinner("Executing command")
def exec_command_sync(  # pylint: disable=too-many-arguments
        resource: str, command: Tuple[str], namespace: str, tasks: List[str],
        containers: List[str], quiet: bool, tty: bool):

    # Convert containers from tuple to list if necessary
    specified_container = list(containers) if containers else []
    specified_tasks = list(tasks) if tasks else []

    exec_command(resource, command, namespace, specified_tasks,
                 specified_container, quiet, tty)


def exec_command(  # pylint: disable=too-many-arguments disable=too-many-locals disable=too-many-branches
        resource: str, command: Tuple[str], namespace: str,
        specified_tasks: Union[List[str], List[None]],
        specified_container: Union[List[str],
                                   List[None]], quiet: bool, tty: bool):
    """
    Executes a specified command within a container of a resource.

    This function supports executing commands in various modes, including direct execution \
        and TTY (interactive) mode.
    It is capable of targeting specific clusters, tasks (pods), and containers, providing \
        flexibility in how commands
    are executed across the infrastructure. It handles both single and multiple targets \
        with appropriate checks
    and balances to ensure the command execution context is correctly established.

    Parameters:
        resource (str): The name of the resource within which the command is to be executed.
        command (Tuple[str]): The command to execute, represented as a tuple of strings.
        namespace (str): The Kubernetes namespace where the resource is located.
        specified_tasks (List[str]): A list of specific tasks (pods) to target for command \
            execution.
            In TTY mode, only a single task can be targeted.
        specified_container (List[str]): A list of container names within the specified \
            tasks where
            the command should be executed. TTY mode supports only a single container.
        quiet (bool): If True, suppresses output.
        tty (bool): If True, executes the command in TTY (interactive) mode.

    Raises:
        click.ClickException: For various conditions such as no command \
            specified, multiple targets specified in TTY mode, etc.

    Returns:
        None: Results of command execution are printed to standard output. In non-TTY mode,
              outputs are directly printed. In TTY mode, a streaming session is initiated.

    Note:
        The function validates the specified clusters, tasks, and containers \
            against the available resources
        and configurations to ensure valid execution contexts. It also handles \
            the dynamic construction \
            of the execution
        dictionary (`exec_dict`) used to frame the execution request.
    """
    from skyshift.cli.cli_utils import \
        stream_cli_object  # pylint: disable=import-outside-toplevel

    if len(command) == 0:
        raise click.ClickException("No command specified.")

    if tty:
        if len(specified_tasks) > 1:
            raise click.ClickException(
                "Multiple tasks specified. TTY mode is only supported for a single task. \
                    Defaulting to the first running task in the job.")
        if len(specified_container) > 1:
            raise click.ClickException(
                "Multiple containers specified. TTY mode is only supported for a single container."
            )
        if not quiet:
            click.echo(
                "Warning: TTY is enabled. This is not recommended for non-interactive sessions."
            )
    if len(specified_tasks) == 0:
        click.echo("No tasks specified. Connecting to all tasks...")
        specified_tasks = [None]

    if len(specified_container) == 0:
        click.echo("No containers specified. Connecting to all containers...")
        specified_container = [None]

    command_str = json.dumps(command)

    for selected_task in specified_tasks:
        for container in specified_container:
            exec_dict = {
                "kind": "exec",
                "metadata": {
                    "namespace": namespace,
                },
                "spec": {
                    "quiet": quiet,
                    "tty": tty,
                    "task": selected_task,
                    "resource": resource,
                    "container": container,
                    "command": quote(command_str).replace('/', '%-2-F-%2-'),
                },
            }
            if not quiet and tty:
                print("Opening the next TTY session...")
            stream_cli_object(exec_dict)


cli.add_command(exec_command_sync)

# ==============================================================================
# User API as CLI


@click.command('register',
               help="""
    
    The register command registers a new user in the system within SkyShift based on an invitation.
    
    Username should be 4-50 characters long composed of upper or lower case alphabetics, digits and/or _.
    Password must be 5 or more characters.
    
    This command allows for the registration of a new user account, which is necessary for accessing
    and interacting with the system. It requires a username, password, and an invite key, to ensure
    that only authorized users can register.

    Examples:
        1. **Register a New User**:
    
           .. code-block:: bash
    
               skyctl register newuser mypassword --invite=abcd1234 --email=newuser@example.com
    
           This command registers a new user with the username `newuser` and the password `mypassword`.
           The user is validated using the invite key `abcd1234` and the email address `newuser@example.com`
           is associated with the account for notifications and recovery.

    """)
@click.argument('username', required=True)
@click.argument('password', required=True)
@click.option('--invite',
              '-inv',
              required=True,
              help='Invite key sent by admin.')
@click.option('--email',
              default=None,
              required=False,
              help='Email address of the user.')
@halo_spinner("Registering user")
def register(username, email, password, invite):  # pylint: disable=redefined-outer-name

    from skyshift.cli.cli_utils import \
        register_user  # pylint: disable=import-outside-toplevel

    register_user(username, email, password, invite)


cli.add_command(register)


@click.command('login',
               help="""
    
    Logs a user into SkyShift using a username and password. This command authenticates
    a user based on the provided credentials. It is important to note that this login
    command does not change the current active user session but merely performs login
    authentication.

    Examples:
        1. **Login as a User**:
    
           .. code-block:: bash
    
               skyctl login myusername mypassword
    
           This command logs in the user with the username `myusername` and the password `mypassword`.
           The user is authenticated based on the provided credentials, but the active user session
           remains unchanged.

    """)
@click.argument('username', required=True)
@click.argument('password', required=True)
@halo_spinner("Logging in")
def login(username, password):
    from skyshift.cli.cli_utils import \
        login_user  # pylint: disable=import-outside-toplevel

    login_user(username, password)


cli.add_command(login)


@click.command('invite',
               help="""

    Creates a new invitation key for user registration, allowing outputting in JSON format.
    This command generates an invitation key that can be used for registering new users
    into SkyShift. It can be configured to associate specific roles with the invite, which
    will then be assigned to the user upon registration.
    
    Examples:
        1. **Create a Simple Invite**:
        
           .. code-block:: bash
        
               skyctl invite
        
           This command generates a new invitation key without any associated roles. The invite key will
           be printed to the console.
        
        2. **Create an Invite with Roles**:
        
           .. code-block:: bash
        
               skyctl invite --role=admin --role=developer
        
           This command generates an invitation key associated with the `admin` and `developer` roles.
           When a user registers using this invite, they will be granted the specified roles.
        
        3. **Create an Invite and Output in JSON Format**:
           .. code-block:: bash
        
               skyctl invite --json
        
           This command generates an invitation key and outputs it in JSON format. The JSON object will
           include the invite key under the key 'invite'.

    """)
@click.option(
    '--json',
    is_flag=True,
    default=False,
    help='Output the invite in json format if succeeds. Key is \'invite\'.')
@click.option('-r',
              '--role',
              multiple=True,
              help='Enter ROLE names intended as part of the invite.')
@halo_spinner("Creating invite")
def invite(json, role):  # pylint: disable=redefined-outer-name

    from skyshift.cli.cli_utils import \
        create_invite  # pylint: disable=import-outside-toplevel

    create_invite(json, list(role))


cli.add_command(invite)


@click.command('revoke_invite',
               help="""

    The revoke invite command allows revoking an existing invitation key.
    This means the user will not be able to use it in the future for registering
    and account with SkySfhit.

    Examples:    
    
    1. **Revoke an Invitation Key**:
    
    .. code-block:: bash

        skyctl revoke_invite abcd1234

    This command revokes the invitation key `abcd1234`. After revocation, the
    key is invalid, and any attempt to use it for registration will fail.
    
    """)
@click.argument('invite', required=True)
@halo_spinner("Revoking invite")
def revoke_invite(invite):  # pylint: disable=redefined-outer-name
    from skyshift.cli.cli_utils import \
        revoke_invite_req  # pylint: disable=import-outside-toplevel

    revoke_invite_req(invite)


cli.add_command(revoke_invite)


@config.command(name="use-context",
                aliases=["use-ctx", "swap-context", "swap-ctx"],
                help="""
    
    Switches the current active context in SkyShift to the specified one. This command
    allows the user to change the active configuration context to another one as
    specified in the '.skyconf/config.yaml' file. This is useful for managing different
    configurations under the same CLI session.

    Examples:
        1. **Switch to a Different Context**:
    
           .. code-block:: bash
    
               skyctl config use-context dev-environment
    
           This command switches the active context to `dev-environment`. The new context configuration
           is loaded, and all subsequent commands will use this context until it is changed again.
        
    """)
@click.argument('name', required=True)
@halo_spinner("Switching context")
def use_sky_context(name: str, spinner):

    from skyshift.cli.cli_utils import \
        use_context  # pylint: disable=import-outside-toplevel

    if not name:
        spinner.warn("No new context is specified. Nothing is changed.")
        return

    use_context(name)


@click.command(name="status",
               help="""

    The status command displays the current status of clusters, available resources,
    and recent jobs in SkyShift.

    This command provides the following:
    - The total available resources of clusters in the 'READY' state.
    - A list of the newest 10 running jobs. Useful for monitoring and administration.

    Example:
    .. code-block:: bash

        skyctl status

    This command displays the status of all clusters in SkyShift, including the total
    available resources in clusters that are in the 'READY' state. It also lists the
    newest 10 running jobs, giving a snapshot of the system's current activity.

    """)
@halo_spinner("Fetching status")
def status():  # pylint: disable=too-many-locals

    from skyshift.api_client import (  # pylint: disable=import-outside-toplevel
        ClusterAPI, JobAPI)
    from skyshift.cli.cli_utils import (  # pylint: disable=import-outside-toplevel
        calculate_total_resources, display_running_jobs,
        get_oldest_cluster_age, get_table_str, print_table)
    from skyshift.globals import \
        APP_NAME  # pylint: disable=import-outside-toplevel
    from skyshift.templates.cluster_template import (  # pylint: disable=import-outside-toplevel
        Cluster, ClusterList, ClusterMeta, ClusterSpec, ClusterStatus,
        ClusterStatusEnum)

    cluster_list = ClusterAPI().list().objects
    click.echo(f"\n{Fore.BLUE}{Style.BRIGHT}Clusters{Style.RESET_ALL}",
               nl=False)
    cluster_table_str = get_table_str('cluster',
                                      ClusterList(objects=cluster_list))
    click.echo(cluster_table_str, nl=False)

    # Create the separator line with the same length as the longest line in the table
    longest_line_length = max(
        len(line) for line in cluster_table_str.split('\n'))
    separator_line = "=" * longest_line_length
    click.echo('\n+\n' + separator_line, nl=False)

    total_resources, available_resources = calculate_total_resources(
        cluster_list)

    # Determine the status for the aggregate cluster
    aggregate_cluster_status = ClusterStatusEnum.READY.value if \
        any(cluster.status.status == ClusterStatusEnum.READY.value for cluster in cluster_list) \
            else ClusterStatusEnum.ERROR.value

    # Create aggregate cluster (sum of all existing READY clusters)
    total_cluster = Cluster(metadata=ClusterMeta(
        name='Merged-Cluster',
        creation_timestamp=get_oldest_cluster_age(cluster_list)),
                            spec=ClusterSpec(manager=APP_NAME),
                            status=ClusterStatus(
                                status=aggregate_cluster_status,
                                capacity=total_resources,
                                allocatable_capacity=available_resources))
    total_cluster_list = ClusterList(objects=[total_cluster])

    # Print aggregate cluster
    print_table('cluster', total_cluster_list)

    job_list = JobAPI().list()
    display_running_jobs(job_list)


cli.add_command(status)


@get.command(name="users", aliases=["user"])
@halo_spinner("Fetching users")
def get_users():
    """Fetches all users."""
    from skyshift.cli.cli_utils import (  # pylint: disable=import-outside-toplevel
        get_cli_object, print_table)

    api_response = get_cli_object(object_type="user")
    print_table('user', api_response)

@delete.command(name="user", aliases=["users"])
@click.argument("username", required=True)
@halo_spinner("Deleting user")
def delete_users(username: str):
    """Deletes a user by username."""
    from skyshift.cli.cli_utils import \
        delete_user  # pylint: disable=import-outside-toplevel

    delete_user(object_type="user", name=username)

@click.command(name="port-forward", help="""
    Forward one or more local ports to a resource.
    This command allows you to forward local ports to a resource managed by SkyShift,
    similar to the `kubectl port-forward` command, but for SkyShift managed resources.
    You can specify the resource, ports to forward, and optionally the Kubernetes context and namespace.

    Examples:

        1. **Forward a Local Port to a Resource in a Specific Context and Namespace**:

           .. code-block:: bash

               skyctl port-forward pod/my-pod 8080:80 --namespace my-namespace --manager=k8 --context my-k8s-context
                Forwarding from 127.0.0.1:8080 -> 8080
                Forwarding from [::1]:8080 -> 8080
                ⠹ Started port-forwarding

           This command forwards local port `8080` to port `80` on the pod `my-pod` in the `my-namespace` namespace,
           using the Kubernetes context `my-k8s-context`.

        2. **Forward Multiple Ports to a Service Without Specifying Context**:

           .. code-block:: bash

               skyctl port-forward service/my-service 8080:80 8443:443 --manager=k8

           This command forwards local ports `8080` and `8443` to ports `80` and `443` on the service `my-service`
           in the default namespace, using the default Kubernetes context.

    Note:

    - The `--manager` option is required and must be set for Kubernetes resources.
    - The `--context` option is optional. If provided, it specifies the Kubernetes context to use for port forwarding.
    - The `--namespace` option specifies the namespace of the resource. Defaults to `'default'` if not provided.

    """)
@click.argument("resource", required=True)
@click.argument("ports", required=True, nargs=-1)
@click.option("--namespace",
              type=str,
              default="default",
              show_default=True,
              help="Namespace corresponding to the resource's location.")
@click.option("--manager",
              required=True,
              help="Resource manager type (e.g., 'k8'). Only 'k8' is supported.")
@click.option("--context",
              type=str,
              default=None,
              help="Kubernetes context to use for port forwarding.")
@halo_spinner("Started port-forwarding")
def port_forward(resource: str, ports: Tuple[str], namespace: str, manager: str, context: str, spinner):
    """
    Forward one or more local ports to a pod or service.
    This CLI command is similar to Kubectl's port forward but for SkyShift managed objects.
    """
    from skyshift.cli.cli_utils import port_forward_util

    try:
        port_forward_util(resource, ports, namespace, manager, context)
    except Exception as e:
        spinner.fail(f"Port forwarding failed: {str(e)}")
        raise click.ClickException(f"Port forwarding failed: {str(e)}")

cli.add_command(port_forward)

if __name__ == '__main__':
    cli()
