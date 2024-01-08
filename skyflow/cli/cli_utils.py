from typing import List

import click
from tabulate import tabulate
from skyflow.api_client import *
from skyflow.globals import DEFAULT_NAMESPACE
from skyflow.templates import Cluster, TaskStatusEnum, Object, ObjectList


NAMESPACED_API_OBJECTS = {
    'job': JobAPI,
    'filterpolicy': FilterPolicyAPI,
    'service': ServiceAPI,
    'endpoints': EndpointsAPI,
}
NON_NAMESPACED_API_OBJECTS = {
    'cluster': ClusterAPI,
    'namespace': NamespaceAPI,
    'link': LinkAPI,
}
ALL_API_OBJECTS = {**NON_NAMESPACED_API_OBJECTS, **NAMESPACED_API_OBJECTS}


def fetch_api_client_object(object_type: str, namespace: str = None):
    is_namespace_object = object_type in NAMESPACED_API_OBJECTS
    if is_namespace_object:
        api_object = NAMESPACED_API_OBJECTS[object_type](namespace=namespace)
    else:
        api_object = NON_NAMESPACED_API_OBJECTS[object_type]()
    return api_object

def create_cli_object(config: dict):
    namespace = config['metadata'].get('namespace', DEFAULT_NAMESPACE)
    object_type = config['kind'].lower()
    api_object = fetch_api_client_object(object_type, namespace)
    api_response = api_object.create(config)
    click.echo(f"Created {object_type} {config['metadata']['name']}.")
    return api_response

def get_cli_object(object_type: str, name: str = None, namespace: str = None, watch: bool = False):
    api_object = fetch_api_client_object(object_type, namespace)
    if watch:
        api_response = api_object.watch()
        for event in api_response:
            click.echo(event)
        return None
    else:
        if name is None:
            api_response = api_object.list()
        else:
            api_response = api_object.get(name=name)
    return api_response

def delete_cli_object(object_type: str, name: str = None, namespace: str = None):
    api_object = fetch_api_client_object(object_type, namespace)
    api_response = api_object.delete(name=name)
    click.echo(f"Deleted {object_type} {name}.")
    return api_response


def print_cluster_table(cluster_list):
    if isinstance(cluster_list, ObjectList):
        cluster_list = cluster_list.objects
    else:
        cluster_list = [cluster_list]
    field_names = ["NAME", "MANAGER", "RESOURCES", "STATUS"]
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
    if isinstance(job_list, ObjectList):
        job_list = job_list.objects
    else:
        job_list = [job_list]
    field_names = ["NAME", "CLUSTER", "REPLICAS", "RESOURCES", "NAMESPACE", "STATUS"]
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
    if isinstance(namespace_list, ObjectList):
        namespace_list = namespace_list.objects
    else:
        namespace_list = [namespace_list]
    field_names = ["NAME", "STATUS"]
    table_data = []

    for entry in namespace_list:
        name = entry.get_name()
        status = entry.get_status()
        table_data.append([name, status])

    table = tabulate(table_data, field_names, tablefmt="plain")
    click.echo(f'{table}\r')


def print_filter_table(job_list: List[dict]):
    if isinstance(job_list, ObjectList):
        job_list = job_list.objects
    else:
        job_list = [job_list]
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



def print_service_table(service_list: List[dict]):
    if isinstance(service_list, ObjectList):
        service_list = service_list.objects
    else:
        service_list = [service_list]
    field_names = [
        "NAME", "TYPE", "CLUSTER-IP", "EXTERNAL-IP", "PORTS", "CLUSTER",
    ]
    table_data = []

    for entry in service_list:
        name = entry.get_name()
        type = entry.spec.type
        ports = entry.spec.ports
        cluster_ip = entry.spec.cluster_ip
        external_ip = entry.status.external_ip
        cluster = entry.spec.primary_cluster
        port_str = ''
        # port_str = '80:8080; ...'
        for idx, p in enumerate(ports):
            if idx == len(ports)-1:
                port_str += f'{p.port}:{p.target_port}'
            else:
                port_str += f'{p.port}:{p.target_port}; '
        table_data.append([name, type, cluster_ip, external_ip, port_str, cluster])

    table = tabulate(table_data, field_names, tablefmt="plain")
    click.echo(f'{table}\r')


def print_link_table(link_list):
    if isinstance(link_list, ObjectList):
        link_list = link_list.objects
    else:
        link_list = [link_list]
    field_names = ["NAME", "SOURCE", "TARGET", "STATUS"]
    table_data = []

    for entry in link_list:
        name = entry.get_name()
        source = entry.spec.source_cluster
        target = entry.spec.target_cluster
        status = entry.get_status()
        table_data.append([name, source, target, status])

    table = tabulate(table_data, field_names, tablefmt="plain")
    click.echo(f'{table}\r')

def print_endpoints_table(endpoints_list):
    if isinstance(endpoints_list, ObjectList):
        endpoints_list = endpoints_list.objects
    else:
        endpoints_list = [endpoints_list]
    field_names = ["NAME", "NAMESPACE", "ENDPOINTS"]
    table_data = []

    for entry in endpoints_list:
        name = entry.get_name()
        namespace = entry.get_namespace()
        endpoints = entry.spec.endpoints
        endpoints_str = ''
        for cluster, endpoint_obj in endpoints.items():
            endpoints_str += f'{cluster}: {endpoint_obj.num_endpoints}\n'
        table_data.append([name, namespace, endpoints_str])

    table = tabulate(table_data, field_names, tablefmt="plain")
    click.echo(f'{table}\r')