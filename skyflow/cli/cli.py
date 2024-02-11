"""
Skyflow CLI.
"""
import os
from typing import List, Tuple

import click
import yaml
from click_aliases import ClickAliasedGroup

from skyflow.cli.cli_utils import (create_cli_object, delete_cli_object,
                                   get_cli_object, print_cluster_table,
                                   print_endpoints_table, print_filter_table,
                                   print_job_table, print_link_table,
                                   print_namespace_table, print_service_table)


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


cli.add_command(create)
cli.add_command(get)
cli.add_command(delete)
cli.add_command(apply)


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
@click.option("--run",
              type=str,
              default="sleep 10",
              help="Run command for the job.")
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
):  #pylint: disable=too-many-arguments, too-many-locals
    """Adds a new job."""
    labels = dict(labels)
    envs = dict(envs)

    resource_dict = {
        "cpus": cpus,
        "gpus": gpus,
        "memory": memory,
    }
    if accelerators:
        acc_type, acc_count = accelerators.split(":")
        resource_dict[acc_type] = int(acc_count)

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
def create_filter_policy(name, namespace, labelselector, includecluster,
                         excludecluster):
    """Adds a new filter policy."""
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
def delete_link(name):
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
):  #pylint: disable=too-many-arguments, too-many-locals
    """Creates a new service."""
    ports_list = [{
        "port": port,
        "target_port": target_port,
        "protocol": "TCP"
    } for port, target_port in ports]
    if isinstance(selector, tuple):
        selector = [selector]
    selector_dict = {s[0]: s[1] for s in selector}
    assert cluster is not None, "Service `cluster` must be specified."

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
@get.command(name="endpoints", aliases=["endpoint"])
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


@delete.command(name="endpoints", aliases=["endpoint"])
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
