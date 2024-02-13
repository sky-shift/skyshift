"""
Skyflow CLI.
"""
import os
import re
from typing import Dict, List, Tuple

import click
import yaml
from click_aliases import ClickAliasedGroup

from skyflow.cli.cli_utils import (create_cli_object, delete_cli_object,
                                   fetch_job_logs, get_cli_object,
                                   print_cluster_table, print_endpoints_table,
                                   print_filter_table, print_job_table,
                                   print_link_table, print_namespace_table,
                                   print_service_table)
from skyflow.templates.cluster_template import Cluster
from skyflow.templates.job_template import RestartPolicyEnum
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
    """Validates if the given value matches the required pattern and is less than 253 characters."""
    pattern = re.compile(r'^[a-z0-9]([-a-z0-9]{0,251}[a-z0-9])?$')
    return bool(pattern.fullmatch(value))


def validate_label_selector(labelselector: List[Tuple[str, str]]) -> bool:
    """Validates label selectors."""
    for key, value in labelselector:
        if not validate_input_string(key) or not validate_input_string(value):
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


def validate_resources(resources: Dict[str, float],
                       accelerators: str | None = None) -> bool:
    """Validates resource specifications."""
    valid_resource_types = {"cpus", "gpus", "memory", "disk"}
    if accelerators:  # If accelerators are specified, validate their format as well
        if not re.match(r'^[A-Za-z0-9]+:[0-9]+$', accelerators):
            return False
        acc_type, _ = accelerators.split(":")
        valid_resource_types.add(acc_type)

    return all(key in valid_resource_types and value >= 0
               for key, value in resources.items())


def validate_restart_policy(policy: str) -> bool:
    """Validates if the given restart policy is supported."""
    return RestartPolicyEnum.has_value(policy)
cli.add_command(logs)


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
@click.argument("name", required=True)
@click.option(
    "--manager",
    default="k8",
    show_default=True,
    required=True,
    help="Type of cluster manager",
)
def create_cluster(name: str, manager: str):
    """Attaches a new cluster."""
    if manager not in ["k8"]:
        click.echo(f"Unsupported manager_type: {manager}")
        raise click.BadParameter(f"Unsupported manager_type: {manager}")

    if not validate_input_string(name):
        click.echo("Error: Name format is invalid.", err=True)
        raise click.BadParameter("Name format is invalid.")

    cluster_dictionary = {
        "kind": "Cluster",
        "metadata": {
            "name": name,
        },
        "spec": {
            "manager": manager
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
    default="gcr.io/sky-burst/skyburst:latest",
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
    help=
    "Number of GPUs per task. Note that these GPUs can be any type of GPU.",
)
@click.option(
    "--accelerators",
    "-a",
    type=str,
    default=None,
    help="Type of accelerator resource to use (e.g. T4:1, V100:2)",
)
@click.option("--memory",
              type=float,
              default=0,
              help="Total memory (RAM) per task in MB.")
@click.option("--run", type=str, default="", help="Run command for the job.")
@click.option("--replicas",
              type=int,
              default=1,
              help="Number of replicas to run job.")
@click.option("--restart_policy",
              type=str,
              default="Always",
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
    if not validate_input_string(name) or not validate_input_string(namespace):
        raise click.BadParameter("Invalid name or namespace format.")

    if not validate_label_selector(labels):
        raise click.BadParameter("Invalid label selector format.")

    if not validate_image_format(image):
        raise click.BadParameter("Invalid image format.")

    resource_dict = {"cpus": cpus, "gpus": gpus, "memory": memory}
    if accelerators:
        if not validate_resources(resource_dict, accelerators):
            raise click.BadParameter("Invalid resource or accelerator format.")
    else:
        if not validate_resources(resource_dict):
            raise click.BadParameter("Invalid resource format.")

    if not validate_restart_policy(restart_policy):
        raise click.BadParameter("Invalid restart policy.")

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
    help="Namespace corresponding to job's location.",
)
@click.option("--watch", default=False, is_flag=True, help="Performs a watch.")
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
        raise click.BadParameter(f"The namespace name '{name}' is invalid.\
                  It must match the pattern [a-z0-9]([-a-z0-9]*[a-z0-9])?")

    namespace_dictionary = {
        "kind": "Namespace",
        "metadata": {
            "name": name,
        },
    }
    create_cli_object(namespace_dictionary)


@get.command(name="namespace", aliases=["namespaces"])
@click.argument("name", required=False, default=None)
@click.option("--watch", default=False, is_flag=True, help="Performs a watch.")
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
        raise click.BadParameter("Link name is invalid.")

    if not validate_input_string(source) or not validate_input_string(target):
        raise click.BadParameter("Source or target cluster name is invalid.")

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
    help="Namespace corresponding to service's location.",
)
@click.option("--service_type",
              "-t",
              type=str,
              default="ClusterIP",
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
        raise click.BadParameter("Service name is invalid.")
    if not validate_input_string(namespace):
        raise click.BadParameter("Namespace is invalid.")

    # Validate service type
    if not ServiceType.__members__.get(service_type):
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
        raise click.BadParameter("Selector is invalid.")

    # Validate ports
    for port, target_port in ports:
        if not 0 < port <= 65535:
            raise click.BadParameter(f"Port {port} is out of valid range.")
        if not 0 < target_port <= 65535:
            raise click.BadParameter(
                f"Target port {target_port} is out of valid range.")

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
              help="Namespace for the endpoints.")
@click.option("--num_endpoints", type=int, help="Number of endpoints.")
@click.option("--exposed",
              is_flag=True,
              default=False,
              help="Whether the endpoints are exposed to the cluster.")
@click.option("--primary_cluster",
              type=str,
              default="auto",
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
        raise click.BadParameter("Invalid name for endpoints.")

    if not validate_input_string(namespace):
        raise click.BadParameter("Invalid namespace name.")

    if num_endpoints is not None and num_endpoints < 0:
        raise click.BadParameter("Number of endpoints must be non-negative.")

    if exposed and not primary_cluster:
        raise click.BadParameter(
            "Exposed endpoints must specify a primary cluster.")

    if primary_cluster != "auto" and not cluster_exists(primary_cluster):
        raise click.BadParameter("Invalid primary cluster name.")

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
    help="Namespace corresponding to service`s locaton.",
)
def delete_endpoints(name: str, namespace: str):
    """Removes/detaches a cluster from Sky Manager."""
    delete_cli_object(object_type="endpoints", namespace=namespace, name=name)
