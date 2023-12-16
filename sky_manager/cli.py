from typing import List

import click
from tabulate import tabulate

from sky_manager.launch_sky_manager import launch_sky_manager
from sky_manager.api_client import *
from sky_manager.templates import Cluster, TaskStatusEnum, ResourceEnum


@click.group()
def cli():
    pass


@click.group()
def create():
    """Create an object."""
    pass


@click.group()
def get():
    """Get an object."""
    pass


@click.group()
def delete():
    """Delete an object."""
    pass


@click.group()
def watch():
    """Watch for events over objects."""
    pass


cli.add_command(create)
cli.add_command(get)
cli.add_command(delete)
cli.add_command(watch)


#==============================================================================
# Cluster API as CLI
@create.command(name='cluster')
@click.argument('name', required=True)
@click.option('--manager',
              default='k8',
              show_default=True,
              required=True,
              help='Type of cluster manager')
def create_cluster(name: str, manager: str):
    """Attaches a new cluster."""
    if manager not in ['k8']:
        click.echo(f"Unsupported manager_type: {manager}")
        return

    cluster_dictionary = {
        'kind': 'Cluster',
        'metadata': {
            'name': name,
        },
        'spec': {
            'manager': manager
        }
    }
    api_response = ClusterAPI().create(cluster_dictionary)
    click.echo(f"Created cluster {name}.")
    return api_response


@get.command(name='clusters')
@click.option('--watch', default=False, is_flag=True, help='Performs a watch.')
def list_clusters(watch: bool):
    """Lists all attached clusters."""
    cluster_api_obj = ClusterAPI()
    if watch:
        api_response = cluster_api_obj.watch()
        for event in api_response:
            click.echo(event)
    else:
        api_response = cluster_api_obj.list()
        print_cluster_table(api_response.objects)
        return api_response


@get.command(name='cluster')
@click.argument('name', required=True)
def get_cluster(name):
    """Gets cluster."""
    cluster_api_obj = ClusterAPI()
    api_response = cluster_api_obj.get(name)
    print_cluster_table([api_response])
    return api_response


@delete.command(name='cluster')
@click.argument('name', required=True)
def delete_cluster(name):
    """Removes/detaches a cluster from Sky Manager."""
    api_response = ClusterAPI().delete(name)
    click.echo(f"Deleted cluster {name}.")
    return api_response


#==============================================================================


# Job API as CLI
@create.command(name='job')
@click.argument('name', required=True)
@click.option('--namespace',
              type=str,
              default='default',
              help='Namespace corresponding to job\'s location.')
@click.option('--labels',
              '-l',
              type=(str, str),
              multiple=True,
              default=[],
              help='Key-value pairs for job labels')
@click.option('--image',
              type=str,
              default='gcr.io/sky-burst/skyburst:latest',
              help='Image to run the job in (any docker registry image).')
@click.option('--envs',
              '-e',
              type=(str, str),
              multiple=True,
              default=[],
              help='Pass in environment variables to the job.')
@click.option('--cpus',
              type=float,
              default=1,
              help='Number of CPUs per task.')
@click.option('--gpus',
              type=int,
              default=0,
              help='Number of GPUs per task. Note that these GPUs can be any type of GPU.')
@click.option('--accelerators', '-a', type=str, default=None, help='Type of accelerator resource to use (e.g. T4:1, V100:2)')
@click.option('--memory',
              type=float,
              default=0,
              help='Total memory (RAM) per task in MB.')
@click.option('--run',
              type=str,
              default='sleep 10',
              help='Run command for the job.')
@click.option('--replicas',
              type=int,
              default=1,
              help='Number of replicas to run job.')
def create_job(name, namespace, labels, image, envs, cpus, gpus, accelerators, memory, run, replicas):
    """Adds a new job."""
    labels = dict(labels)
    envs = dict(envs)

    resource_dict = {
                'cpus': cpus,
                'gpus': gpus,
                'memory': memory,
    }
    if accelerators:
        acc_type, acc_count = accelerators.split(':')
        resource_dict[acc_type] = int(acc_count)

    job_dictionary = {
        'kind': 'Job',
        'metadata': {
            'name': name,
            'namespace': namespace,
            'labels': labels,
        },
        'spec': {
            'image': image,
            'envs': envs,
            'resources': resource_dict,
            'run': run,
            'replicas': replicas,
        }
    }
    job_api_obj = JobAPI(namespace=namespace)
    api_response = job_api_obj.create(job_dictionary)
    click.echo(f"Created job {name}.")
    return api_response


@get.command(name='jobs')
@click.option('--namespace',
              type=str,
              default='default',
              help='Namespace corresponding to job\'s location.')
@click.option('--watch', default=False, is_flag=True, help='Performs a watch.')
def list_jobs(namespace: str, watch: bool):
    """Lists all jobs across all clusters."""
    job_api_obj = JobAPI(namespace=namespace)
    if watch:
        api_response = job_api_obj.watch()
        for event in api_response:
                click.echo(event)
    else:
        api_response = job_api_obj.list()
        print_job_table(api_response.objects)
        return api_response


@get.command(name='job')
@click.argument('name', required=True)
@click.option('--namespace',
              type=str,
              default='default',
              help='Namespace corresponding to job\'s location.')
def get_job(name: str, namespace: str):
    """Fetches a job."""
    job_api_obj = JobAPI(namespace=namespace)
    api_response = job_api_obj.get(name)
    print_job_table([api_response])
    return api_response


@delete.command(name='job')
@click.argument('name', required=True)
@click.option('--namespace',
              type=str,
              default='default',
              help='Namespace corresponding to job\'s location.')
def delete_job(name: str, namespace: str):
    """Deletes a job."""
    job_api_obj = JobAPI()
    api_response = job_api_obj.delete(name)
    click.echo(f"Deleted job {name}.")
    return api_response


#==============================================================================


# Namspace API as CLI
@create.command(name='namespace')
@click.argument('name', required=True)
def create_namespace(name: str):
    """Creates a new namespace."""

    namespace_dictionary = {
        'kind': 'Namespace',
        'metadata': {
            'name': name,
        },
    }
    namespace_api_obj = NamespaceAPI()
    api_response = namespace_api_obj.create(namespace_dictionary)
    click.echo(f"Created namespace {name}.")
    return api_response


@get.command(name='namespaces')
@click.option('--watch', default=False, is_flag=True, help='Performs a watch.')
def list_namespaces(watch: bool):
    """Lists all attached clusters."""
    namespace_api_obj = NamespaceAPI()
    if watch:
        api_response = namespace_api_obj.watch()
        for event in api_response:
            click.echo(event)
    else:
        api_response = namespace_api_obj.list()
        print_namespace_table(api_response.objects)
        return api_response


@get.command(name='namespace')
@click.argument('name', required=True)
def get_namespace(name: str):
    """Gets cluster."""
    namespace_api_obj = NamespaceAPI()
    api_response = namespace_api_obj.get(name)
    print_namespace_table([api_response])
    return api_response


@delete.command(name='namespace')
@click.argument('name', required=True)
def delete_namespace(name: str):
    """Removes/detaches a cluster from Sky Manager."""
    namespace_api_obj = NamespaceAPI()
    api_response = namespace_api_obj.delete(name)
    click.echo(f"Deleted namespace {name}.")
    return api_response

# FilterPolicy API as CLI
@create.command(name='filterPolicy')
@click.argument('name', required=True)
@click.option('--namespace',
              type=str,
              default='default',
              help='Namespace corresponding to policy\'s location.')
@click.option('--labelSelector',
              '-l',
              type=(str, str),
              multiple=True,
              default=[],
              help='Key-value pairs for selecting over labels.')
@click.option('--includeCluster',
              '-i',
              type=str,
              multiple=True,
              default=[],
              help='Clusters to include in scheduling..')
@click.option('--excludeCluster',
              '-e',
              type=str,
              multiple=True,
              default=[],
              help='Clusters to exclude in scheduling..')
def create_filter_policy(name, namespace, labelselector, includecluster,
                         excludecluster):
    """Adds a new filter policy."""
    labels = dict(labelselector)

    obj_dictionary = {
        'kind': 'FilterPolicy',
        'metadata': {
            'name': name,
            'namespace': namespace,
        },
        'spec': {
            'clusterFilter': {
                'include': includecluster,
                'exclude': excludecluster,
            },
            'labelsSelector': labels
        }
    }
    api_obj = FilterPolicyAPI(namespace=namespace)
    api_response = api_obj.create(obj_dictionary)
    click.echo(f"Created filter policy {name}.")
    return api_response


@get.command(name='filterPolicies')
@click.option('--namespace',
              type=str,
              default='default',
              help='Namespace corresponding to policy\'s location.')
@click.option('--watch', default=False, is_flag=True, help='Performs a watch.')
def list_filter_policies(namespace: str, watch: bool):
    """Lists all jobs across all clusters."""
    api_obj = FilterPolicyAPI(namespace=namespace)
    if watch:
        api_response = api_obj.watch()
        for event in api_response:
            click.echo(event)
    else:
        api_response = api_obj.list()
        print_filter_table(api_response.objects)
        return api_response


@get.command(name='filterPolicy')
@click.argument('name', required=True)
@click.option('--namespace',
              type=str,
              default='default',
              help='Namespace corresponding to policy\'s location.')
def get_filter_policy(name: str, namespace: str):
    """Fetches a job."""
    api_obj = FilterPolicyAPI(namespace=namespace)
    api_response = api_obj.get(name)
    print_filter_table([api_response])
    return api_response


@delete.command(name='filterPolicy')
@click.argument('name', required=True)
@click.option('--namespace',
              type=str,
              default='default',
              help='Namespace corresponding to policy\'s location.')
def delete_filter_policy(name: str, namespace: str):
    """Deletes a job."""
    api_obj = FilterPolicyAPI(namespace=namespace)
    api_response = api_obj.delete(name)
    click.echo(f"Deleted filter policy {name}.")
    return api_response


#==============================================================================


def print_cluster_table(cluster_list: List[Cluster]):
    field_names = ["Name", "Manager", "Resources", "Status"]
    table_data = []

    def gather_resources(data):
        if data is None or len(data) == 0:
            return {}
        aggregated_data = {}
        for inner_dict in data.values():
            for key, value in inner_dict.items():
                if key in aggregated_data:
                    aggregated_data[key] += value
                else:
                    aggregated_data[key] = value
        return aggregated_data

    for entry in cluster_list:
        name = entry.get_name()
        manager_type = entry.spec.manager


        resources = entry.status.capacity
        allocatable_resources = entry.status.allocatable_capacity
        resources = gather_resources(resources)
        allocatable_resources = gather_resources(allocatable_resources)
        resources_str = ''
        for key in resources.keys():
            if resources[key] == 0:
                continue
            if key not in allocatable_resources:
                available_resources = '???'
            else:
                available_resources = allocatable_resources[key]
            resources_str += f'{key}: {available_resources}/{resources[key]}\n'
        if not resources_str:
            resources_str = '{}'
        status = entry.get_status()
        table_data.append([name, manager_type, resources_str, status])

    table = tabulate(table_data, field_names, tablefmt="plain")
    click.echo(f'{table}\r')


def print_job_table(job_list: List[dict]):
    field_names = ["Name", "Cluster", "Replicas", "Resources", "Namespace", "Status"]
    table_data = []

    for entry in job_list:
        name = entry.get_name()
        clusters = entry.status.replica_status
        namespace = entry.get_namespace()
        resources = entry.spec.resources
        resources_str = ''
        for key in resources.keys():
            if resources[key] == 0:
                continue
            resources_str += f'{key}: {resources[key]}\n'

        status = entry.status.conditions[-1]['type']
        if clusters:
            for cluster_name, cluster_replica_status in clusters.items():
                replica_count = sum(cluster_replica_status.values())
                active_count = 0
                if TaskStatusEnum.RUNNING.value in cluster_replica_status:
                    active_count += cluster_replica_status[TaskStatusEnum.RUNNING.value]
                
                if TaskStatusEnum.COMPLETED.value in cluster_replica_status:
                    active_count += cluster_replica_status[TaskStatusEnum.COMPLETED.value]
                
                if active_count == 0:
                    if TaskStatusEnum.FAILED.value in cluster_replica_status:
                        status = TaskStatusEnum.FAILED.value
                    elif TaskStatusEnum.EVICTED.value in cluster_replica_status:
                        status = TaskStatusEnum.EVICTED.value
                    else:
                        status = TaskStatusEnum.PENDING.value
                elif active_count != replica_count:
                    status = TaskStatusEnum.RUNNING.value
                else:
                    is_single_specific_key = len(cluster_replica_status) == 1 and TaskStatusEnum.COMPLETED.value in cluster_replica_status
                    if is_single_specific_key:
                        status = TaskStatusEnum.COMPLETED.value
                    else:
                        status = TaskStatusEnum.RUNNING.value

                table_data.append(
                    [name, cluster_name, f'{active_count}/{replica_count}', resources_str, namespace, status])
        else:
            table_data.append([name, '', f'0/{entry.spec.replicas}', resources_str, namespace, status])

    table = tabulate(table_data, field_names, tablefmt="plain")
    click.echo(f'{table}\r')


def print_namespace_table(namespace_list: List[dict]):
    field_names = ["Name", "Status"]
    table_data = []

    for entry in namespace_list:
        name = entry.get_name()
        status = entry.get_status()
        table_data.append([name, status])

    table = tabulate(table_data, field_names, tablefmt="plain")
    click.echo(f'{table}\r')


def print_filter_table(job_list: List[dict]):
    field_names = [
        "Name", "Include", "Exclude", "Labels", "Namespace", "Status"
    ]
    table_data = []

    for entry in job_list:
        name = entry.get_name()
        include = entry.spec.cluster_filter.include
        exclude = entry.spec.cluster_filter.exclude
        namespace = entry.get_namespace()
        labels = entry.spec.labels_selector
        status = entry.get_status()
        table_data.append([name, include, exclude, labels, namespace, status])

    table = tabulate(table_data, field_names, tablefmt="plain")
    click.echo(f'{table}\r')
