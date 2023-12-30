import click
from click_aliases import ClickAliasedGroup

from skyflow.api_client import *
from skyflow.cli.cli_utils import *

@click.group()
def cli():
    pass


@click.group(cls=ClickAliasedGroup)
def create():
    """Create an object."""
    pass


@click.group(cls=ClickAliasedGroup)
def get():
    """Get an object."""
    pass


@click.group(cls=ClickAliasedGroup)
def delete():
    """Delete an object."""
    pass

cli.add_command(create)
cli.add_command(get)
cli.add_command(delete)

#==============================================================================
# Cluster API as CLI
@create.command(name='cluster', aliases=['clusters'])
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
    create_cli_object(cluster_dictionary)


@get.command(name='cluster', aliases=['clusters'])
@click.argument('name', required=False, default=None)
@click.option('--watch', '-w', default=False, is_flag=True, help='Performs a watch.')
def get_clusters(name: str, watch: bool):
    """Gets a cluster (or clusters if None is specified)."""
    api_response = get_cli_object(object_type = 'cluster', name=name, watch=watch)
    print_cluster_table(api_response)

@delete.command(name='cluster', aliases=['clusters'])
@click.argument('name', required=True)
def delete_cluster(name):
    """Removes/detaches a cluster from Sky Manager."""
    delete_cli_object(object_type= 'cluster', name=name)

#==============================================================================
# Job API as CLI
@create.command(name='job', aliases=['jobs'])
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
    create_cli_object(job_dictionary)


@get.command(name='job', aliases=['jobs'])
@click.argument('name', default=None, required=False)
@click.option('--namespace',
              type=str,
              default='default',
              help='Namespace corresponding to job\'s location.')
@click.option('--watch', default=False, is_flag=True, help='Performs a watch.')
def get_job(name: str, namespace: str, watch: bool):
    """Fetches a job."""
    api_response = get_cli_object(object_type = 'job', name=name, namespace=namespace, watch=watch)
    print_job_table(api_response)


@delete.command(name='job', aliases=['jobs'])
@click.argument('name', required=True)
@click.option('--namespace',
              type=str,
              default='default',
              help='Namespace corresponding to job\'s location.')
def delete_job(name: str, namespace: str):
    """Deletes a job."""
    delete_cli_object(object_type= 'job', name=name, namespace=namespace)

#==============================================================================
# Namspace API as CLI
@create.command(name='namespace', aliases=['namespaces'])
@click.argument('name', required=True)
def create_namespace(name: str):
    """Creates a new namespace."""
    namespace_dictionary = {
        'kind': 'Namespace',
        'metadata': {
            'name': name,
        },
    }
    create_cli_object(namespace_dictionary)


@get.command(name='namespace', aliases=['namespaces'])
@click.argument('name', required=False, default=None)
@click.option('--watch', default=False, is_flag=True, help='Performs a watch.')
def get_namespace(name: str, watch: bool):
    """Gets all namespaces."""
    api_response = get_cli_object(object_type = 'namespace', name=name, watch=watch)
    print_namespace_table(api_response)


@delete.command(name='namespace', aliases=['namespaces'])
@click.argument('name', required=True)
def delete_namespace(name: str):
    """Removes/detaches a cluster from Sky Manager."""
    delete_cli_object(object_type= 'namespace', name=name)

#==============================================================================
# FilterPolicy API as CLI
@create.command(name='filterPolicy', aliases=['filterPolicies', 'filterpolicy', 'filterpolicies'])
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
    create_cli_object(obj_dictionary)


@get.command(name='filterPolicy', aliases=['filterPolicies', 'filterpolicy', 'filterpolicies'])
@click.argument('name', required=False, default=None)
@click.option('--namespace',
              type=str,
              default='default',
              help='Namespace corresponding to policy\'s location.')
@click.option('--watch', default=False, is_flag=True, help='Performs a watch.')
def get_filter_policy(name: str, namespace: str, watch: bool):
    """Fetches a job."""
    api_response = get_cli_object(object_type = 'filterpolicy', name=name, namespace=namespace, watch=watch)
    print_filter_table(api_response)


@delete.command(name='filterPolicy', aliases=['filterPolicies', 'filterpolicy', 'filterpolicies'])
@click.argument('name', required=True)
@click.option('--namespace',
              type=str,
              default='default',
              help='Namespace corresponding to policy\'s location.')
def delete_filter_policy(name: str, namespace: str):
    """Deletes a job."""
    delete_cli_object(object_type= 'filterpolicy', name=name, namespace=namespace)

#==============================================================================
# Link CLI
@create.command(name='link', aliases=['links'])
@click.argument('name', required=True)
@click.option('--source',
              '-s',
              required=True,
              help='Source cluster name')
@click.option('--target',
              '-t',
              required=True,
              help='Target cluster name')
def create_link(name: str, source: str, target: str):
    """Creates a new link between two clusters."""

    obj_dict = {
        'kind': 'Link',
        'metadata': {
            'name': name,
        },
        'spec': {
            'source_cluster': source,
            'target_cluster': target,
        }
    }
    create_cli_object(obj_dict)


@get.command(name='link', aliases=['links'])
@click.argument('name', required=False, default=None)
@click.option('--watch', '-w', default=False, is_flag=True, help='Performs a watch.')
def get_links(name: str, watch: bool):
    """Gets link (or links if None is specified)."""
    api_response = get_cli_object(object_type = 'link', name=name, watch=watch)
    print_link_table(api_response)

@delete.command(name='link', aliases=['links'])
@click.argument('name', required=True)
def delete_link(name):
    """Removes/detaches a cluster from Sky Manager."""
    delete_cli_object(object_type= 'link', name=name)

