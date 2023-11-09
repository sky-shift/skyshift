from typing import List

import click
from tabulate import tabulate

from sky_manager.launch_sky_manager import launch_sky_manager
from sky_manager.api_client import job_api
from sky_manager.api_client import *


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
    cluster_api_obj = ClusterAPI()
    api_response = cluster_api_obj.create(cluster_dictionary)
    if 'error' in api_response:
        click.echo(api_response['error'])
    else:
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
            if 'error' in event:
                click.echo(event['error'])
            else:
                click.echo(event)
    else:
        api_response = cluster_api_obj.list()
        if 'error' in api_response:
            click.echo(api_response['error'])
        else:
            print_cluster_table(api_response['items'])
        return api_response


@get.command(name='cluster')
@click.argument('name', required=True)
def get_cluster(name):
    """Gets cluster."""
    cluster_api_obj = ClusterAPI()
    api_response = cluster_api_obj.get(name)
    if 'error' in api_response:
        click.echo(api_response['error'])
    else:
        print_cluster_table([api_response])
    return api_response


@delete.command(name='cluster')
@click.argument('name', required=True)
def delete_cluster(name):
    """Removes/detaches a cluster from Sky Manager."""
    cluster_api_obj = ClusterAPI()
    api_response = cluster_api_obj.delete(name)
    if 'error' in api_response:
        click.echo(api_response['error'])
    else:
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
@click.option('--resources',
              '-r',
              type=(str, int),
              multiple=True,
              default=[('cpu', 1)],
              help='Resources required for the job.')
@click.option('--run',
              type=str,
              default='sleep 10',
              help='Run command for the job.')
def create_job(name, namespace, labels, image, resources, run):
    """Adds a new job."""
    labels = dict(labels)
    resources = dict(resources)

    job_dictionary = {
        'kind': 'Job',
        'metadata': {
            'name': name,
            'namespace': namespace,
            'labels': labels,
        },
        'spec': {
            'image': image,
            'resources': resources,
            'run': run,
        }
    }
    job_api_obj = JobAPI(namespace=namespace)
    api_response = job_api_obj.create(job_dictionary)
    if 'error' in api_response:
        click.echo(api_response['error'])
    else:
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
            if 'error' in event:
                click.echo(event['error'])
            else:
                click.echo(event)
    else:
        api_response = job_api_obj.list()
        if 'error' in api_response:
            click.echo(api_response['error'])
        else:
            print_job_table(api_response['items'])
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
    if 'error' in api_response:
        click.echo(api_response['error'])
    else:
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
    if 'error' in api_response:
        click.echo(api_response['error'])
    else:
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
    if 'error' in api_response:
        click.echo(api_response['error'])
    else:
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
            if 'error' in event:
                click.echo(event['error'])
            else:
                click.echo(event)
    else:
        api_response = namespace_api_obj.list()
        if 'error' in api_response:
            click.echo(api_response['error'])
        else:
            print_namespace_table(api_response['items'])
        return api_response


@get.command(name='namespace')
@click.argument('name', required=True)
def get_namespace(name: str):
    """Gets cluster."""
    namespace_api_obj = NamespaceAPI()
    api_response = namespace_api_obj.get(name)
    if 'error' in api_response:
        click.echo(api_response['error'])
    else:
        print_namespace_table([api_response])
    return api_response


@delete.command(name='namespace')
@click.argument('name', required=True)
def delete_namespace(name: str):
    """Removes/detaches a cluster from Sky Manager."""
    namespace_api_obj = NamespaceAPI()
    api_response = namespace_api_obj.delete(name)
    if 'error' in api_response:
        click.echo(api_response['error'])
    else:
        click.echo(f"Deleted namespace {name}.")
    return api_response


#==============================================================================


# Admin server as CLI
@cli.command()
@click.option('--host',
              default='localhost',
              show_default=True,
              help='IP Address of the Sky Manager controller.')
@click.option(
    '--api_server_port',
    default=50051,
    show_default=True,
    help=
    'API Server port for the API server running on the Sky Manager controller.'
)
def launch_controller(host: str, api_server_port: int):
    """Lauches Sky Manager, including the Skylet controller and scheduler controller."""
    click.echo(
        f'Launching Sky Manager on {host}, API server on {host}:{api_server_port}.'
    )
    launch_sky_manager()


#==============================================================================


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
    if 'error' in api_response:
        click.echo(api_response['error'])
    else:
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
            if 'error' in event:
                click.echo(event['error'])
            else:
                click.echo(event)
    else:
        api_response = api_obj.list()
        if 'error' in api_response:
            click.echo(api_response['error'])
        else:
            print_filter_table(api_response['items'])
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
    if 'error' in api_response:
        click.echo(api_response['error'])
    else:
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
    if 'error' in api_response:
        click.echo(api_response['error'])
    else:
        click.echo(f"Deleted filter policy {name}.")
    return api_response


#==============================================================================


def print_cluster_table(cluster_list: List[dict]):
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
        name = entry['metadata']['name']
        manager_type = entry['spec']['manager']

        resources = gather_resources(entry['status']['capacity'])
        allocatable_resources = gather_resources(
            entry['status']['allocatable'])
        resources_str = ''
        for key in resources.keys():
            if key not in allocatable_resources:
                available_resources = '???'
            else:
                available_resources = allocatable_resources[key]
            resources_str += f'{key}: {available_resources}/{resources[key]}\n'
        if not resources_str:
            resources_str = '{}'
        status = entry['status']['status']
        table_data.append([name, manager_type, resources_str, status])

    table = tabulate(table_data, field_names, tablefmt="plain")
    click.echo(f'{table}\r')


def print_job_table(job_list: List[dict]):
    field_names = ["Name", "Cluster", "Resources", "Namespace", "Status"]
    table_data = []

    for entry in job_list:
        name = entry['metadata']['name']
        cluster_name = entry['status']['cluster']
        namespace = entry['metadata']['namespace']
        resources = entry['spec']['resources']
        resources_str = ''
        for key in resources.keys():
            resources_str += f'{key}: {resources[key]}\n'

        status = entry['status']['status']
        table_data.append(
            [name, cluster_name, resources_str, namespace, status])

    table = tabulate(table_data, field_names, tablefmt="plain")
    click.echo(f'{table}\r')


def print_namespace_table(namespace_list: List[dict]):
    field_names = ["Name", "Status"]
    table_data = []

    for entry in namespace_list:
        name = entry['metadata']['name']
        status = entry['status']['status']
        table_data.append([name, status])

    table = tabulate(table_data, field_names, tablefmt="plain")
    click.echo(f'{table}\r')


def print_filter_table(job_list: List[dict]):
    field_names = [
        "Name", "Include", "Exclude", "Labels", "Namespace", "Status"
    ]
    table_data = []

    for entry in job_list:
        name = entry['metadata']['name']
        include = entry['spec']['clusterFilter']['include']
        exclude = entry['spec']['clusterFilter']['exclude']
        namespace = entry['metadata']['namespace']
        labels = entry['spec']['labelsSelector']
        status = entry['status']['status']
        table_data.append([name, include, exclude, labels, namespace, status])

    table = tabulate(table_data, field_names, tablefmt="plain")
    click.echo(f'{table}\r')
