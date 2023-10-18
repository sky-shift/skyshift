from typing import List

import click
from tabulate import tabulate

from sky_manager.launch_sky_manager import launch_sky_manager
from sky_manager.api_client import cluster_api, job_api


@click.group()
def cli():
    pass


#==============================================================================


# Cluster API as CLI
@cli.command()
@click.option('--name', required=True, help='Name of the cluster')
@click.option('--manager_type',
              default='k8',
              show_default=True,
              required=True,
              help='Type of cluster manager')
def create_cluster(name: str, manager_type: str):
    """Adds a new cluster to Sky Manager."""
    if manager_type not in ['k8']:
        click.echo(f"Unsupported manager_type: {manager_type}")
        return

    cluster_dictionary = {
        'kind': 'Cluster',
        'metadata': {
            'name': name,
        },
        'spec': {
            'manager': manager_type
        }
    }
    api_response = cluster_api.CreateCluster(cluster_dictionary)
    if 'error' in api_response:
        click.echo(api_response['error'])
    else:
        click.echo(f"Created cluster {name}.")
    return api_response


@cli.command()
def list_clusters():
    """Lists all clusters."""
    api_response = cluster_api.ListClusters()
    print_cluster_table(api_response['items'])
    return api_response


@cli.command()
@click.option('--name', required=True, help='Name of the cluster')
def get_cluster(name):
    """Fetches a cluster."""
    api_response = cluster_api.GetCluster(cluster=name)
    if 'error' in api_response:
        click.echo(api_response['error'])
    else:
        print_cluster_table([api_response])
    return api_response


@cli.command()
@click.option('--name', required=True, help='Name of the cluster')
def delete_cluster(name):
    """Removes a cluster from Sky Manager."""
    api_response = cluster_api.DeleteCluster(cluster=name)
    if 'error' in api_response:
        click.echo(api_response['error'])
    else:
        click.echo(f"Deleted cluster {name}.")
    return api_response


#==============================================================================


# Job API as CLI
@cli.command()
@click.option('--name', required=True, help='Name of the cluster')
@click.option('--labels',
              '-l',
              type=(str, str),
              multiple=True,
              default=[],
              help='Key-value pairs for job labels')
@click.option(
    '--image',
    type=str,
    default='gcr.io/sky-burst/skyburst:latest',
    help='Image to run the job in. (Can be VM image or docker image).')
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
def create_job(name, labels, image, resources, run):
    """Adds a new job."""
    labels = dict(labels)
    resources = dict(resources)

    job_dictionary = {
        'kind': 'Job',
        'metadata': {
            'name': name,
            'labels': labels,
        },
        'spec': {
            'image': image,
            'resources': resources,
            'run': run,
        }
    }
    api_response = job_api.CreateJob(job_dictionary)
    if 'error' in api_response:
        click.echo(api_response['error'])
    else:
        click.echo(f"Created job {name}.")
    return api_response


@cli.command()
def list_jobs():
    """Lists all jobs across all clusters."""
    api_response = job_api.ListJobs()
    print_job_table(api_response['items'])
    return api_response


@cli.command()
@click.option('--name', required=True, help='Name of the cluster')
def get_job(name):
    """Fetches a job."""
    api_response = job_api.GetJob(job=name)
    if 'error' in api_response:
        click.echo(api_response['error'])
    else:
        print_job_table([api_response])
    return api_response


@cli.command()
@click.option('--name', required=True, help='Name of the cluster')
def delete_job(name):
    """Deletes a job."""
    api_response = job_api.DeleteJob(job=name)
    if 'error' in api_response:
        click.echo(api_response['error'])
    else:
        click.echo(f"Deleted job {name}.")
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

        status = entry['status']['status']
        table_data.append([name, manager_type, resources_str, status])

    table = tabulate(table_data, field_names, tablefmt="plain")
    click.echo(f'{table}\r')


def print_job_table(job_list: List[dict]):
    field_names = ["Name", "Cluster", "Resources", "Status"]
    table_data = []

    for entry in job_list:
        name = entry['metadata']['name']
        cluster_name = entry['status']['cluster']

        resources = entry['spec']['resources']
        resources_str = ''
        for key in resources.keys():
            resources_str += f'{key}: {resources[key]}\n'

        status = entry['status']['status']
        table_data.append([name, cluster_name, resources_str, status])

    table = tabulate(table_data, field_names, tablefmt="plain")
    click.echo(f'{table}\r')
