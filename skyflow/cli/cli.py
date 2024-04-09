# pylint: disable=too-many-lines
"""
Skyflow CLI.
"""
import json
import os
import re
from typing import Dict, List, Tuple, Union
from urllib.parse import quote

import click
import yaml
from click_aliases import ClickAliasedGroup

from skyflow.cli.cli_utils import (create_cli_object, create_invite,
                                   delete_cli_object, fetch_job_logs,
                                   get_cli_object, login_user,
                                   print_cluster_table, print_endpoints_table,
                                   print_filter_table, print_job_table,
                                   print_link_table, print_namespace_table,
                                   print_role_table, print_service_table,
                                   register_user, revoke_invite_req,
                                   stream_cli_object, switch_context)
from skyflow.cloud.utils import cloud_cluster_dir
from skyflow.cluster_manager.manager import SUPPORTED_CLUSTER_MANAGERS
from skyflow.templates.cluster_template import Cluster
from skyflow.templates.job_template import RestartPolicyEnum
from skyflow.templates.resource_template import AcceleratorEnum, ResourceEnum
from skyflow.templates.service_template import ServiceType


@click.group()
def cli():
    """Skyflow CLI."""
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


cli.add_command(create)
cli.add_command(get)
cli.add_command(delete)
cli.add_command(apply)
cli.add_command(logs)


def validate_input_string(value: str) -> bool:
    """
    Validates if the given key matches the required pattern including
    an optional domain prefix and is less than 253 characters.
    """
    if value.startswith("kubernetes.io/") or value.startswith("k8s.io/"):
        return False
    pattern = re.compile(
        r'^([a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*/)?[a-z0-9]([-a-z0-9-.]{0,251}[a-z0-9])?$'  # pylint: disable=line-too-long
    )
    return bool(pattern.fullmatch(value))


def validate_value_string(value: str) -> bool:
    """Validates if the given value matches the required pattern and is less than 63 characters."""
    pattern = re.compile(r'^[a-z0-9]([-a-z0-9-.]{0,61}[a-z0-9])?$')
    return bool(pattern.fullmatch(value))


def validate_label_selector(labelselector: List[Tuple[str, str]]) -> bool:
    """Validates label selectors."""
    for key, value in labelselector:
        if not validate_input_string(key) or not validate_value_string(value):
            click.echo(f"Error: Invalid label selector: {key}:{value}",
                       err=True)
            return False
    return True


def cluster_exists(name: str) -> bool:
    """Checks if the given cluster exists in the database."""
    api_response: Cluster = get_cli_object(object_type="cluster", name=name)
    return api_response is not None and api_response.metadata.name == name


def validate_image_format(image: str) -> bool:
    """Validates if the given image matches the Docker image format."""
    pattern = re.compile(
        r'^([a-zA-Z0-9.-]+)?(:[a-zA-Z0-9._-]+)?(/[a-zA-Z0-9._/-]+)?(:[a-zA-Z0-9._-]+|@sha256:[a-fA-F0-9]{64})?$'  # pylint: disable=line-too-long
    )
    return bool(pattern.fullmatch(image))


def validate_resources(resources: Dict[str, float]) -> bool:
    """
    Validates resource specifications.
    """
    valid_resource_types = {item.value for item in ResourceEnum}
    return all(key in valid_resource_types and value >= 0
               for key, value in resources.items())


def validate_accelerator(accelerator: Union[str, None]) -> bool:
    """Validates accelerator specification format and checks if it's a valid type."""
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
    return RestartPolicyEnum.has_value(policy)


# Apply as CLI
@click.command(name="apply")
@click.option("--file",
              "-f",
              required=True,
              help="Path to config file (YAML).")
def apply_config(file: str):
    """Converts a config file to a Skyflow object."""
    if file is None:
        raise Exception("File must be specified.")

    absolute_config_path = os.path.abspath(os.path.expanduser(file))
    if not os.path.exists(absolute_config_path):
        raise Exception(f"File {absolute_config_path} does not exist.")

    with open(os.path.expanduser(absolute_config_path), "r") as config_file:
        config_dict = yaml.safe_load(config_file)

    create_cli_object(config_dict)


cli.add_command(apply_config)


# ==============================================================================
# Cluster API as CLI
@create.command(name="cluster", aliases=["clusters"])
@click.argument('name', required=True)
@click.option('--manager',
              default='k8',
              show_default=True,
              required=True,
              help='Cluster manager type (e.g. k8, slurm).')
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
@click.option('--provision',
              is_flag=True,
              help='True if cluster needs to be provisioned on the cloud.')
def create_cluster(  # pylint: disable=too-many-arguments
        name: str, manager: str, cpus: str, memory: str, disk_size: int,
        accelerators: str, ports: List[str], num_nodes: int, cloud: str,
        region: str, provision: bool):
    """Attaches a new cluster."""
    if manager not in SUPPORTED_CLUSTER_MANAGERS:
        click.echo(f"Unsupported manager_type: {manager}")
        raise click.BadParameter(f"Unsupported manager_type: {manager}")

    if not validate_input_string(name):
        click.echo("Error: Name format is invalid.", err=True)
        raise click.BadParameter("Name format is invalid.")

    if ports:
        ports = list(ports)

    cluster_dictionary = {
        "kind": "Cluster",
        "metadata": {
            "name": name,
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
            'config_path':
            "~/.kube/config" if not provision else
            f"{cloud_cluster_dir(name)}/kube_config_rke_cluster.yml",
        },
    }
    create_cli_object(cluster_dictionary)


@get.command(name="cluster", aliases=["clusters"])
@click.argument("name", required=False, default=None)
@click.option("--watch",
              "-w",
              default=False,
              is_flag=True,
              help="Performs a watch.")
def get_clusters(name: str, watch: bool):
    """Gets a cluster (or clusters if None is specified)."""

    api_response = get_cli_object(object_type="cluster",
                                  name=name,
                                  watch=watch)
    print_cluster_table(api_response)


@delete.command(name="cluster", aliases=["clusters"])
@click.argument("name", required=True)
def delete_cluster(name):
    """Removes/detaches a cluster from Sky Manager."""
    delete_cli_object(object_type="cluster", name=name)


# ==============================================================================
# Job API as CLI
@create.command(name="job", aliases=["jobs"])
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
              default=RestartPolicyEnum.ALWAYS.value,
              show_default=True,
              help="Restart policy for job tasks.")
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
):  # pylint: disable=too-many-arguments
    """Adds a new job."""
    # Validate inputs
    if not validate_input_string(name):
        raise click.BadParameter("Invalid namespace format.")

    if not validate_input_string(namespace):
        raise click.BadParameter("Invalid namespace format.")

    if not validate_label_selector(labels):
        raise click.BadParameter("Invalid label selector format.")

    if not validate_image_format(image):
        raise click.BadParameter("Invalid image format.")

    if not validate_restart_policy(restart_policy):
        raise click.BadParameter("Invalid restart policy.")

    resource_dict = {
        ResourceEnum.CPU.value: cpus,
        ResourceEnum.GPU.value: gpus,
        ResourceEnum.MEMORY.value: memory
    }
    if not validate_resources(resource_dict):
        raise click.BadParameter("Invalid resource format.")

    if not validate_accelerator(accelerators):
        raise click.BadParameter("Invalid accelerator format.")

    labels = dict(labels)
    envs = dict(envs)

    job_dictionary = {
        "kind": "Job",
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": labels,
        },
        "spec": {
            "image": image,
            "envs": envs,
            "resources": resource_dict,
            "run": run,
            "replicas": replicas,
            "restart_policy": restart_policy,
        },
    }
    create_cli_object(job_dictionary)


@get.command(name="job", aliases=["jobs"])
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
def get_job(name: str, namespace: str, watch: bool):
    """Fetches a job."""
    api_response = get_cli_object(object_type="job",
                                  name=name,
                                  namespace=namespace,
                                  watch=watch)
    print_job_table(api_response)


@click.command(name="logs")
@click.argument("name", default=None, required=False)
@click.option(
    "--namespace",
    type=str,
    default="default",
    show_default=True,
    help="Namespace corresponding to job's namespace.",
)
def job_logs(name: str, namespace: str):
    """Fetches a job's logs."""
    fetch_job_logs(name=name, namespace=namespace)


cli.add_command(job_logs)


@delete.command(name="job", aliases=["jobs"])
@click.argument("name", required=True)
@click.option(
    "--namespace",
    type=str,
    default="default",
    show_default=True,
    help="Namespace corresponding to job's location.",
)
def delete_job(name: str, namespace: str):
    """Deletes a job."""
    delete_cli_object(object_type="job", name=name, namespace=namespace)


# ==============================================================================
# Namespace API as CLI
@create.command(name="namespace", aliases=["namespaces"])
@click.argument("name", required=True)
def create_namespace(name: str):
    """Creates a new namespace."""
    # Validate the namespace name
    if not validate_input_string(name):
        raise click.BadParameter(f"The namespace name '{name}' is invalid.")

    namespace_dictionary = {
        "kind": "Namespace",
        "metadata": {
            "name": name,
        },
    }
    create_cli_object(namespace_dictionary)


@get.command(name="namespace", aliases=["namespaces"])
@click.argument("name", required=False, default=None)
@click.option("--watch",
              "-w",
              default=False,
              is_flag=True,
              help="Performs a watch.")
def get_namespace(name: str, watch: bool):
    """Gets all namespaces."""
    api_response = get_cli_object(object_type="namespace",
                                  name=name,
                                  watch=watch)
    print_namespace_table(api_response)


@delete.command(name="namespace", aliases=["namespaces"])
@click.argument("name", required=True)
def delete_namespace(name: str):
    """Removes/detaches a cluster from Sky Manager."""
    delete_cli_object(object_type="namespace", name=name)


# ==============================================================================
# FilterPolicy API as CLI
@create.command(name="filterPolicy",
                aliases=["filterPolicies", "filterpolicy", "filterpolicies"])
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
def create_filter_policy(name: str, namespace: str,
                         labelselector: List[Tuple[str, str]],
                         includecluster: List[str], excludecluster: List[str]):
    """Adds a new filter policy."""
    # Validate name and namespace
    if not validate_input_string(name) or not validate_input_string(namespace):
        click.echo("Error: Name or namespace format is invalid.", err=True)
        raise click.BadParameter("Name or namespace format is invalid.")

    # Validate label selectors
    if not validate_label_selector(labelselector):
        click.echo("Error: Label selector format is invalid.", err=True)
        raise click.BadParameter("Label selector format is invalid.")

    # Check if any input cluster is also an output cluster and viceversa
    if any(cluster in includecluster for cluster in excludecluster):
        click.echo("Error: Clusters cannot be both included and excluded.",
                   err=True)
        raise click.BadParameter(
            "Clusters cannot be both included and excluded.")

    # Check if clusters exist
    for cluster_name in set(includecluster + excludecluster):
        if not cluster_exists(cluster_name):
            click.echo(f"Error: Cluster '{cluster_name}' does not exist.",
                       err=True)
            raise click.BadParameter(
                f"Error: Cluster '{cluster_name}' does not exist.")

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
             aliases=["filterPolicies", "filterpolicy", "filterpolicies"])
@click.argument("name", required=False, default=None)
@click.option(
    "--namespace",
    type=str,
    default="default",
    show_default=True,
    help="Namespace corresponding to policy's location.",
)
@click.option("--watch", default=False, is_flag=True, help="Performs a watch.")
def get_filter_policy(name: str, namespace: str, watch: bool):
    """Fetches a job."""
    if not validate_input_string(namespace):
        click.echo("Error: Name or namespace format is invalid.", err=True)
        raise click.BadParameter("Name or namespace format is invalid.")

    api_response = get_cli_object(object_type="filterpolicy",
                                  name=name,
                                  namespace=namespace,
                                  watch=watch)
    print_filter_table(api_response)


@delete.command(name="filterPolicy",
                aliases=["filterPolicies", "filterpolicy", "filterpolicies"])
@click.argument("name", required=True)
@click.option(
    "--namespace",
    type=str,
    default="default",
    show_default=True,
    help="Namespace corresponding to policy's location.",
)
def delete_filter_policy(name: str, namespace: str):
    """Deletes a job."""
    if not validate_input_string(name) or not validate_input_string(namespace):
        click.echo("Error: Name or namespace format is invalid.", err=True)
        raise click.BadParameter("Name or namespace format is invalid.")

    delete_cli_object(object_type="filterpolicy",
                      name=name,
                      namespace=namespace)


# ==============================================================================
# Link CLI
@create.command(name="link", aliases=["links"])
@click.argument("name", required=True)
@click.option("--source", "-s", required=True, help="Source cluster name")
@click.option("--target", "-t", required=True, help="Target cluster name")
def create_link(name: str, source: str, target: str):
    """Creates a new link between two clusters."""

    if not validate_input_string(name):
        raise click.BadParameter(f"Link name {name} is invalid.")

    if not validate_input_string(source):
        raise click.BadParameter(f"Source cluster {source} is invalid.")
    if not validate_input_string(target):
        raise click.BadParameter(f"Target cluster {target} is invalid.")

    if source == target:
        raise click.BadParameter(
            "Source and target clusters cannot be the same.")

    if not cluster_exists(source):
        raise click.BadParameter(f"Source cluster '{source}' does not exist.")
    if not cluster_exists(target):
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


@get.command(name="link", aliases=["links"])
@click.argument("name", required=False, default=None)
@click.option("--watch",
              "-w",
              default=False,
              is_flag=True,
              help="Performs a watch.")
def get_links(name: str, watch: bool):
    """Gets link (or links if None is specified)."""
    api_response = get_cli_object(object_type="link", name=name, watch=watch)
    print_link_table(api_response)


@delete.command(name="link", aliases=["links"])
@click.argument("name", required=True)
def delete_link(name: str):
    """Removes/detaches a cluster from Sky Manager."""
    delete_cli_object(object_type="link", name=name)


# ==============================================================================
# Service API as CLI
@create.command(name="service", aliases=["services", "svc"])
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
              default="ClusterIP",
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
def create_service(
    name: str,
    namespace: str,
    service_type: str,
    selector: List[Tuple[str, str]],
    ports: List[Tuple[int, int]],
    cluster: str,
):  # pylint: disable=too-many-arguments
    """Creates a new service."""
    # Validate service name and namespace
    if not validate_input_string(name):
        raise click.BadParameter(f"Service name {name} is invalid.")
    if not validate_input_string(namespace):
        raise click.BadParameter(f"Namespace {namespace} is invalid.")

    # Validate service type
    if not ServiceType.has_value(service_type):
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
        raise click.BadParameter(f"Selector {selector} is invalid.")

    # Validate ports
    for port, target_port in ports:
        if not 0 < port <= 65535:
            raise click.BadParameter(f"Port {port} is out of valid range.")
        if not 0 < target_port <= 65535:
            raise click.BadParameter(
                f"Target port {target_port} is out of valid range.")

    # @TODO(mluo|acuadron): Implement auto
    # Validate cluster
    if cluster != "auto" and not cluster_exists(cluster):
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


@get.command(name="service", aliases=["services", "svc"])
@click.argument("name", required=False, default=None)
@click.option(
    "--namespace",
    type=str,
    default="default",
    show_default=True,
    help="Namespace corresponding to service`s locaton.",
)
@click.option("--watch", default=False, is_flag=True, help="Performs a watch.")
def get_service(name: str, namespace: str, watch: bool):
    """Gets all services or fetches a specific service."""
    api_response = get_cli_object(object_type="service",
                                  name=name,
                                  namespace=namespace,
                                  watch=watch)
    print_service_table(api_response)


@delete.command(name="service", aliases=["services", "svc"])
@click.argument("name", required=True)
@click.option(
    "--namespace",
    type=str,
    default="default",
    show_default=True,
    help="Namespace corresponding to service`s locaton.",
)
def delete_service(name: str, namespace: str):
    """Removes/detaches a cluster from Sky Manager."""
    delete_cli_object(object_type="service", namespace=namespace, name=name)


# ==============================================================================
# Endpoints API as CLI
@create.command(name="endpoints", aliases=["endpoint", "edp", "edps"])
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
def create_endpoints(  # pylint: disable=too-many-arguments
        name, namespace, num_endpoints, exposed, primary_cluster, selector):
    """Creates a new set of endpoints."""
    # Validate inputs
    if not validate_input_string(name):
        raise click.BadParameter(f"Invalid name {name} for endpoints.")

    if not validate_input_string(namespace):
        raise click.BadParameter(f"Invalid namespace name: {namespace}.")

    if num_endpoints is not None and num_endpoints < 0:
        raise click.BadParameter("Number of endpoints must be non-negative.")

    if exposed and not primary_cluster:
        raise click.BadParameter(
            "Exposed endpoints must specify a primary cluster.")

    if primary_cluster != "auto" and not cluster_exists(primary_cluster):
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


@get.command(name="endpoints", aliases=["endpoint", "edp", "edps"])
@click.argument("name", required=False, default=None)
@click.option(
    "--namespace",
    type=str,
    default="default",
    show_default=True,
    help="Namespace corresponding to service`s locaton.",
)
@click.option("--watch", default=False, is_flag=True, help="Performs a watch.")
def get_endpoints(name: str, namespace: str, watch: bool):
    """Gets all services or fetches a specific service."""
    api_response = get_cli_object(object_type="endpoints",
                                  name=name,
                                  namespace=namespace,
                                  watch=watch)
    print_endpoints_table(api_response)


@delete.command(name="endpoints", aliases=["endpoint", "edp", "edps"])
@click.argument("name", required=True)
@click.option(
    "--namespace",
    type=str,
    default="default",
    show_default=True,
    help="Namespace corresponding to service`s locaton.",
)
def delete_endpoints(name: str, namespace: str):
    """Removes/detaches a cluster from Sky Manager."""
    delete_cli_object(object_type="endpoints", namespace=namespace, name=name)


# ==============================================================================
# Role API as CLI


@create.command(name="role", aliases=["roles"])
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
def create_role(name: str, action: List[str], resource: List[str],
                namespace: List[str], users: List[str]):
    """Create a new role."""

    if not validate_input_string(name):
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


@get.command(name="role", aliases=["roles"])
@click.argument("name", required=False, default=None)
@click.option("--watch",
              "-w",
              default=False,
              is_flag=True,
              help="Performs a watch.")
def get_roles(name: str, watch: bool):
    """Gets a role (or all roles if None is specified)."""
    if name and not validate_input_string(name):
        raise click.BadParameter(f"Name format is invalid: {name}")

    api_response = get_cli_object(object_type="role", name=name, watch=watch)
    print_role_table(api_response)


@delete.command(name="role", aliases=["roles"])
@click.argument("name", required=True)
def delete_role(name):
    """Removes a role."""
    if not validate_input_string(name):
        raise click.BadParameter(f"Name format is invalid: {name}")
    delete_cli_object(object_type="role", name=name)


# ==============================================================================
# Skyflow exec


@click.command(name="exec")
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
def exec_command_sync(  # pylint: disable=too-many-arguments
        resource: str, command: Tuple[str], namespace: str, tasks: List[str],
        containers: List[str], quiet: bool, tty: bool):
    """
    Wrapper for exec_command to parse inputs and change variable names.
    """
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
               help='''\
Register a new user. \'register USERNAME PASSWORD \'
Username should be 4-50 characters long composed of upper or lower case alphabetics, digits and/or _.
Password must be 5 or more characters.
'''
               '  \n ')
@click.argument('username', required=True)
@click.argument('password', required=True)
@click.option('--invite', '-inv', required=True, help='Invite key sent by admin.')
@click.option('--email',
              default=None,
              required=False,
              help='Email address of the user.')
def register(username, email, password, invite):  # pylint: disable=redefined-outer-name
    """
    Register a new user.
    """
    register_user(username, email, password, invite)


cli.add_command(register)


@click.command(
    'login',
    help=
    'Login user. Does NOT change current active user. \'login USERNAME PASSWORD \''
)
@click.argument('username', required=True)
@click.argument('password', required=True)
def login(username, password):
    """
    Login command with username and password.
    """
    login_user(username, password)


cli.add_command(login)


@click.command('invite', help='Create a new invite for registery.')
@click.option(
    '--json',
    is_flag=True,
    default=False,
    help='Output the invite in json format if succeeds. Key is \'invite\'.')
@click.option('-r',
              '--role',
              multiple=True,
              help='Enter ROLE names intended as part of the invite.')
def invite(json, role):  # pylint: disable=redefined-outer-name
    """
    Create a new invite.
    """
    create_invite(json, list(role))


cli.add_command(invite)


@click.command('revoke_invite', help='Revoke created invite.')
@click.argument('invite', required=True)
def revoke_invite(invite):  # pylint: disable=redefined-outer-name
    """
    Revoke an existing invite.
    """
    revoke_invite_req(invite)


cli.add_command(revoke_invite)


@click.command('switch', help='Switch the current context.')
@click.option('--user', default='', help='The active username to use.')
@click.option('-ns',
              '--namespace',
              default='',
              help='The active namespace to use.')
def switch(user, namespace):
    """
    Switch active context of cli.
    """
    if not user and not namespace:
        click.echo("No new context is specified. Nothing is changed.")
        return

    switch_context(user, namespace)


cli.add_command(switch)

if __name__ == '__main__':
    cli()
