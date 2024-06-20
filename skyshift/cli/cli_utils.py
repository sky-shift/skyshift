"""
Utils for SkyShift CLI.
"""
import enum
import io
import json as json_lib
import time
from contextlib import redirect_stdout
from typing import Dict, List, Optional, Union

import click
from colorama import Fore, Style, init
from tabulate import tabulate
from tqdm import tqdm

from skyshift import utils
from skyshift.api_client import (ClusterAPI, EndpointsAPI, FilterPolicyAPI,
                                 JobAPI, LinkAPI, NamespaceAPI, RoleAPI,
                                 ServiceAPI, UserAPI)
# Import API parent class.
from skyshift.api_client.exec_api import ExecAPI
from skyshift.api_client.object_api import APIException, ObjectAPI
from skyshift.globals import DEFAULT_NAMESPACE
from skyshift.templates import (Cluster, ClusterList, FilterPolicy,
                                FilterPolicyList, Job, JobList, Link, LinkList,
                                Namespace, NamespaceList, Object, ObjectList,
                                Service, ServiceList, TaskStatusEnum)
from skyshift.templates.cluster_template import ClusterStatusEnum
from skyshift.templates.job_template import JobStatusEnum
from skyshift.templates.resource_template import ResourceEnum
from skyshift.utils.utils import (API_SERVER_CONFIG_PATH,
                                  compute_datetime_delta, fetch_datetime,
                                  load_manager_config, update_manager_config)

NAMESPACED_API_OBJECTS = {
    "job": JobAPI,
    "filterpolicy": FilterPolicyAPI,
    "service": ServiceAPI,
    "endpoints": EndpointsAPI,
    "exec": ExecAPI,
}
NON_NAMESPACED_API_OBJECTS = {
    "cluster": ClusterAPI,
    "namespace": NamespaceAPI,
    "link": LinkAPI,
    "role": RoleAPI,
    "user": UserAPI
}
ALL_API_OBJECTS = {**NON_NAMESPACED_API_OBJECTS, **NAMESPACED_API_OBJECTS}


class FieldEnum(enum.Enum):
    """
    Enum for common field enums to print in tables.
    """
    NAME = "NAME"
    STATUS = "STATUS"
    AGE = "AGE"
    NAMESPACE = "NAMESPACE"

    def __eq__(self, other):
        if isinstance(other, str):
            return self.value == other
        return super().__eq__(other)


def fetch_api_client_object(object_type: str,
                            namespace: Optional[str] = None) -> ObjectAPI:
    """
    Fetches the API client object for the given object type.
    """

    is_namespace_object = object_type in NAMESPACED_API_OBJECTS
    if is_namespace_object:
        if namespace is None:
            namespace = ""
        api_object: ObjectAPI = NAMESPACED_API_OBJECTS[object_type](
            namespace=namespace)
    else:
        api_object = NON_NAMESPACED_API_OBJECTS[object_type]()
    return api_object


def create_cli_object(config: dict):
    """
    Creates an object through Python API.
    """

    namespace = config["metadata"].get("namespace", DEFAULT_NAMESPACE)
    object_type = config["kind"].lower()
    api_object = fetch_api_client_object(object_type, namespace)
    try:
        api_response = api_object.create(config)
    except APIException as error:
        raise click.ClickException(
            f"\nFailed to create {object_type}: {error}")
    if object_type != "exec":
        click.echo(f"\nCreated {object_type} {config['metadata']['name']}.")
    return api_response


def stream_cli_object(config: dict):
    """
    Creates a bi-directional stream through the Python API.
    """

    namespace = config["metadata"].get("namespace", DEFAULT_NAMESPACE)
    object_type = config["kind"].lower()
    api_object = fetch_api_client_object(object_type, namespace)
    try:
        api_response = api_object.websocket_stream(config)
    except APIException as error:
        raise click.ClickException(
            f"Failed to create {object_type} stream: {error}") from error
    return api_response


def get_cli_object(
    object_type: str,
    name: Optional[str] = None,
    namespace: Optional[str] = None,
    watch: Optional[bool] = False,
):
    """
    Gets an object through Python API.
    """

    api_object = fetch_api_client_object(object_type, namespace)
    try:
        if watch:
            api_response = api_object.watch()
            for event in api_response:
                click.echo(event)
            return None
        if name is None:
            api_response = api_object.list()
        else:
            api_response = api_object.get(name=name)
    except APIException as error:
        raise click.ClickException(f"\nFailed to get {object_type}: {error}")
    return api_response


def delete_cli_object(object_type: str,
                      name: str,
                      namespace: Optional[str] = None):
    """
    Deletes an object through Python API.
    """

    api_object = fetch_api_client_object(object_type, namespace)
    try:
        api_response = api_object.delete(name=name)
    except APIException as error:
        raise click.ClickException(
            f"\nFailed to delete {object_type}: {error}")
    click.echo(f"\nDeleted {object_type} {name}.")
    return api_response


def init_colorama_once():
    """
    Initializes colorama once.
    """
    if not hasattr(init_colorama_once, "initialized"):
        init(autoreset=True)
        init_colorama_once.initialized = True


def print_table(table_type, *args, **kwargs):
    """
    Prints out a table of objects.
    """
    init_colorama_once()
    table_function_map = {
        'cluster': print_cluster_table,
        'job': print_job_table,
        'namespace': print_namespace_table,
        'filterpolicy': print_filter_table,
        'service': print_service_table,
        'link': print_link_table,
        'endpoints': print_endpoints_table,
        'role': print_role_table
    }
    print_function = table_function_map.get(table_type)
    if print_function:
        return print_function(*args, **kwargs)
    raise ValueError("Invalid table type provided")


def fetch_job_logs(name: str, namespace: str):
    """
    Get logs of a Job.
    """

    job_api = JobAPI(namespace=namespace)
    try:
        logs = job_api.logs(name)
        for log in logs:
            click.echo(log)
            click.echo('\n')
    except APIException as error:
        raise click.ClickException(f"\nFailed to fetch logs: {error}")


def _get_object_age(obj: Object) -> str:
    """
    Returns the age of an object.
    """
    creation_str = obj.metadata.creation_timestamp
    obj_age = compute_datetime_delta(creation_str, fetch_datetime())
    return obj_age


def colorize_status(status: str) -> str:
    """
    Returns the status text with appropriate color.
    """
    if status in [ClusterStatusEnum.READY.value, TaskStatusEnum.RUNNING.value]:
        return f"{Fore.GREEN}{status}{Style.RESET_ALL}"
    if status in [ClusterStatusEnum.ERROR.value, TaskStatusEnum.FAILED.value]:
        return f"{Fore.RED}{status}{Style.RESET_ALL}"
    if status in [TaskStatusEnum.COMPLETED.value]:
        return f"{Fore.CYAN}{status}{Style.RESET_ALL}"
    return f"{Fore.YELLOW}{status}{Style.RESET_ALL}"


def print_cluster_table(cluster_list: Union[ClusterList, Cluster]):  # pylint: disable=too-many-locals
    """
    Prints out a table of clusters.
    """
    cluster_lists: List[Cluster] = []
    if isinstance(cluster_list, ObjectList):
        cluster_lists = cluster_list.objects
    else:
        cluster_lists = [cluster_list]
    field_names = [
        FieldEnum.NAME.value, "MANAGER", "LABELS", "RESOURCES",
        FieldEnum.STATUS.value, FieldEnum.AGE.value
    ]
    table_data = []

    def gather_resources(data) -> Dict[str, float]:
        if data is None or len(data) == 0:
            return {}
        aggregated_data: Dict[str, float] = {}
        for inner_dict in data.values():
            for key, value in inner_dict.items():
                if key in aggregated_data:
                    aggregated_data[key] += value
                else:
                    aggregated_data[key] = value
        return aggregated_data

    for entry in cluster_lists:
        name = utils.unsanitize_cluster_name(entry.get_name())
        manager_type = entry.spec.manager

        cluster_resources = entry.status.capacity
        cluster_allocatable_resources = entry.status.allocatable_capacity
        labels_dict = entry.metadata.labels
        labels_str = "\n".join(
            [f"{key}: {value}" for key, value in labels_dict.items()])
        resources = gather_resources(cluster_resources)
        allocatable_resources = gather_resources(cluster_allocatable_resources)
        age = _get_object_age(entry)
        resources_str = ""
        for key in resources:
            if resources[key] == 0:
                continue
            if key not in allocatable_resources:
                available_resources: float = 0
            else:
                available_resources = allocatable_resources[key]
            # Get the first two decimals
            available_resources = round(available_resources, 2)
            resources[key] = round(resources[key], 2)
            if key in [ResourceEnum.MEMORY.value, ResourceEnum.DISK.value]:
                resources_str += f"{key}: {utils.format_resource_units(available_resources)}/{utils.format_resource_units(resources[key])}\n"  # pylint: disable=line-too-long

            else:
                resources_str += f"{key}: {available_resources}/{resources[key]}\n"
        if not resources_str:
            resources_str = "{}"
        status = colorize_status(entry.get_status())
        table_data.append(
            [name, manager_type, labels_str, resources_str, status, age])
    table = None
    if not table_data:
        click.echo("\nNo clusters found.")
    else:
        table = tabulate(table_data, field_names, tablefmt="plain")
        click.echo(f"\n{table}\r")
    return table


def print_job_table(job_list: Union[JobList, Job]):  # pylint: disable=too-many-locals, too-many-branches, too-many-statements
    """
    Prints out a table of jobs.
    """

    job_lists: List[Job] = []
    if isinstance(job_list, ObjectList):
        job_lists = job_list.objects
    else:
        job_lists = [job_list]
    field_names = [
        FieldEnum.NAME.value, "CLUSTER", "REPLICAS", "RESOURCES",
        FieldEnum.NAMESPACE.value, FieldEnum.STATUS.value, FieldEnum.AGE.value
    ]
    table_data = []
    for entry in job_lists:
        name = entry.get_name()
        clusters = entry.status.replica_status
        namespace = entry.get_namespace()
        resources = entry.spec.resources
        age = _get_object_age(entry)
        resources_str = ""
        for key in resources.keys():
            if resources[key] == 0:
                continue
            if key in [ResourceEnum.MEMORY.value, ResourceEnum.DISK.value]:
                resources_str += f"{key}: {utils.format_resource_units(resources[key])}\n"
            else:
                resources_str += f"{key}: {resources[key]}\n"

        status = entry.status.conditions[-1]["type"]
        if clusters:
            for cluster_name, cluster_replica_status in clusters.items():
                cluster_name = utils.unsanitize_cluster_name(cluster_name)
                replica_count = sum(cluster_replica_status.values())
                active_count = 0
                if TaskStatusEnum.RUNNING.value in cluster_replica_status:
                    active_count += cluster_replica_status[
                        TaskStatusEnum.RUNNING.value]

                if TaskStatusEnum.COMPLETED.value in cluster_replica_status:
                    active_count += cluster_replica_status[
                        TaskStatusEnum.COMPLETED.value]

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
                    is_single_specific_key = (len(cluster_replica_status) == 1
                                              and
                                              TaskStatusEnum.COMPLETED.value
                                              in cluster_replica_status)
                    if is_single_specific_key:
                        status = TaskStatusEnum.COMPLETED.value
                    else:
                        status = TaskStatusEnum.RUNNING.value

                table_data.append([
                    name,
                    cluster_name,
                    f"{active_count}/{replica_count}",
                    resources_str,
                    namespace,
                    colorize_status(status),
                    age,
                ])
        else:
            table_data.append([
                name,
                "",
                f"0/{entry.spec.replicas}",
                resources_str,
                namespace,
                colorize_status(status),
                age,
            ])
    table = None
    if not table_data:
        click.echo("\nNo jobs found.")
    else:
        table = tabulate(table_data, field_names, tablefmt="plain")
        click.echo(f"\n{table}\r")
    return table


def print_namespace_table(namespace_list: Union[NamespaceList, Namespace]):
    """
    Prints out a table of namespaces.
    """

    namespace_objs: List[Namespace] = []
    if isinstance(namespace_list, ObjectList):
        namespace_objs = namespace_list.objects
    else:
        namespace_objs = [namespace_list]
    field_names = [
        FieldEnum.NAME.value, FieldEnum.STATUS.value, FieldEnum.AGE.value
    ]
    table_data = []

    for entry in namespace_objs:
        name = entry.get_name()
        status = colorize_status(entry.get_status())
        age = _get_object_age(entry)
        table_data.append([name, status, age])
    table = None
    if not table_data:
        click.echo("\nNo namespaces found.")
    else:
        table = tabulate(table_data, field_names, tablefmt="plain")
        click.echo(f"\n{table}\r")
    return table


def print_filter_table(filter_list: Union[FilterPolicyList, FilterPolicy]):
    """
    Prints out a table of Filter Policies.
    """

    filter_lists: List[FilterPolicy] = []
    if isinstance(filter_list, ObjectList):
        filter_lists = filter_list.objects
    else:
        filter_lists = [filter_list]
    field_names = [
        FieldEnum.NAME.value, "Include", "Exclude", "Labels",
        FieldEnum.NAMESPACE.value, FieldEnum.STATUS.value, FieldEnum.AGE.value
    ]
    # all capital
    field_names = [field.upper() for field in field_names]
    table_data = []

    for entry in filter_lists:
        name = entry.get_name()
        include = entry.spec.cluster_filter.include
        exclude = entry.spec.cluster_filter.exclude
        namespace = entry.get_namespace()
        labels = entry.spec.labels_selector
        status = colorize_status(entry.get_status())
        table_data.append([
            name, include, exclude, labels, namespace, status,
            _get_object_age(entry)
        ])
    table = None
    if not table_data:
        click.echo("\nNo filter policies found.")
    else:
        table = tabulate(table_data, field_names, tablefmt="plain")
        click.echo(f"\n{table}\r")
    return table


def print_service_table(service_list: Union[Service, ServiceList]):  # pylint: disable=too-many-locals
    """
    Prints out a table of services.
    """

    service_lists: List[Service] = []
    if isinstance(service_list, ServiceList):
        service_lists = service_list.objects
    else:
        service_lists = [service_list]
    field_names = [
        FieldEnum.NAME.value,
        "TYPE",
        "CLUSTER-IP",
        "EXTERNAL-IP",
        "PORTS",
        "CLUSTER",
        FieldEnum.NAMESPACE.value,
        FieldEnum.AGE.value,
    ]
    table_data = []

    for entry in service_lists:
        name = entry.get_name()
        service_type = entry.spec.type
        ports = entry.spec.ports
        cluster_ip = entry.spec.cluster_ip
        external_ip = entry.status.external_ip
        cluster = entry.spec.primary_cluster
        namespace = entry.get_namespace()
        port_str = ""
        # port_str = '80:8080; ...'
        for idx, port_obj in enumerate(ports):
            if idx == len(ports) - 1:
                port_str += f"{port_obj.port}:{port_obj.target_port}"
            else:
                port_str += f"{port_obj.port}:{port_obj.target_port}; "
        table_data.append([
            name,
            service_type,
            cluster_ip,
            external_ip,
            port_str,
            cluster,
            namespace,
            _get_object_age(entry),
        ])
    table = None
    if not table_data:
        click.echo("\nNo services found.")
    else:
        table = tabulate(table_data, field_names, tablefmt="plain")
        click.echo(f"\n{table}\r")
    return table


def print_link_table(link_list: Union[Link, LinkList]):
    """
    Prints out a table of links.
    """

    link_lists: List[Link] = []
    if isinstance(link_list, LinkList):
        link_lists = link_list.objects
    else:
        link_lists = [link_list]
    field_names = [
        FieldEnum.NAME.value,
        "SOURCE",
        "TARGET",
        FieldEnum.STATUS.value,
        FieldEnum.AGE.value,
    ]
    table_data = []

    for entry in link_lists:
        name = entry.get_name()
        source = utils.unsanitize_cluster_name(entry.spec.source_cluster)
        target = utils.unsanitize_cluster_name(entry.spec.target_cluster)
        status = colorize_status(entry.get_status())
        age = _get_object_age(entry)
        table_data.append([name, source, target, status, age])
    table = None
    if not table_data:
        click.echo("\nNo links found.")
    else:
        table = tabulate(table_data, field_names, tablefmt="plain")
        click.echo(f"\n{table}\r")


def print_endpoints_table(endpoints_list):
    """
    Prints out a table of Endpoints.
    """

    if isinstance(endpoints_list, ObjectList):
        endpoints_list = endpoints_list.objects
    else:
        endpoints_list = [endpoints_list]

    field_names = [
        FieldEnum.NAME.value, FieldEnum.NAMESPACE.value, "ENDPOINTS",
        FieldEnum.AGE.value
    ]
    table_data = []

    for entry in endpoints_list:
        name = entry.get_name()
        namespace = entry.get_namespace()
        endpoints = entry.spec.endpoints
        endpoints_str = ""
        age = _get_object_age(entry)
        for cluster, endpoint_obj in endpoints.items():
            endpoints_str += f"{cluster}: {endpoint_obj.num_endpoints}\n"
        table_data.append([name, namespace, endpoints_str, age])
    table = None
    if not table_data:
        click.echo("\nNo endpoints found.")
    else:
        table = tabulate(table_data, field_names, tablefmt="plain")
        click.echo(f"\n{table}\r")


def print_role_table(roles_list):
    """
    Prints out a table of Roles.
    """

    if isinstance(roles_list, ObjectList):
        roles_lists = roles_list.objects
    else:
        roles_lists = [roles_list]
    field_names = [
        FieldEnum.NAME.value,
        FieldEnum.AGE.value,
    ]
    table_data = []

    for entry in roles_lists:
        name = entry.get_name()
        age = _get_object_age(entry)
        table_data.append([
            name,
            age,
        ])
    table = None
    if not table_data:
        click.echo("\nNo roles found.")
    else:
        table = tabulate(table_data, field_names, tablefmt="plain")
        click.echo(f"\n{table}\r")


def register_user(username: str, email: str, password: str, invite: str):
    """
    Register user in API Server.
    """

    users_api: UserAPI = fetch_api_client_object("user")  # type: ignore

    try:
        response = users_api.register_user(username, email, password, invite)
        if response.status_code != 200:
            error_details = response.json().get("detail", "Unknown error")
            raise click.ClickException(
                f"Failed to register user: {error_details}")

        click.echo("Registration successful.")
    except APIException as error:
        raise click.ClickException(f"Failed to register user: {error}")


def login_user(username: str, password: str):
    """
    Send login request to API Server; access token stored locally if succeeds.
    """

    users_api: UserAPI = fetch_api_client_object("user")  # type: ignore
    try:
        response = users_api.login_user(username, password)
        if response.status_code != 200:
            error_details = response.json().get("detail", "Unknown error")
            raise click.ClickException(f"Failed to login: {error_details}")

        data = response.json()
        access_token = data.get("access_token")

        # Store the access token to local manager config
        manager_config = load_manager_config()
        found_user = False
        if 'users' not in manager_config:
            manager_config['users'] = []
        for user in manager_config['users']:
            if user['name'] == username:
                user['access_token'] = access_token
                found_user = True
                break
        if not found_user:
            manager_config['users'].append({
                'name': username,
                'access_token': access_token
            })

        update_manager_config(manager_config)
        click.echo(
            f"Login successful. Access token is stored at {API_SERVER_CONFIG_PATH}."
        )
    except APIException as error:
        raise click.ClickException(f"Failed to login: {error}")


def create_invite(json_flag, roles):
    """
    Send create invite request to API Server with the ROLES as to be granted.
    """

    users_api: UserAPI = fetch_api_client_object("user")  # type: ignore
    try:
        response = users_api.create_invite(roles)
        if response.status_code != 200:
            error_details = response.json().get("detail", "Unknown error")
            raise click.ClickException(
                f"Failed to create invite: {error_details}")

        data = response.json()
        if json_flag:
            click.echo(json_lib.dumps(data))
        else:
            invite = data.get("invite")
            click.echo(f"Invitation created successfully. Invite: {invite}")
    except APIException as error:
        raise click.ClickException(f"Failed to create invite: {error}")


def revoke_invite_req(invite: str):
    """
    Send revoke invite request to API Server.
    """

    users_api: UserAPI = fetch_api_client_object("user")  # type: ignore
    try:
        response = users_api.revoke_invite(invite)
        if response.status_code != 200:
            error_details = response.json().get("detail", "Unknown error")
            raise click.ClickException(
                f"Failed to revoke invite: {error_details}")

        data = response.json()
        message = data.get("message")
        click.echo(f"Invitation revoked. {message}")

    except APIException as error:
        raise click.ClickException(f"Failed to create invite: {error}")


def use_context(context_name: str):
    """
    Switch to a specified context name.
    """
    manager_config = load_manager_config()
    contexts = manager_config.get('contexts', [])

    if manager_config.get('current_context', None) == context_name:
        click.echo(f'Current context is already set to {context_name}.')
        return

    if not contexts:
        raise click.ClickException(
            f"No contexts found at {API_SERVER_CONFIG_PATH}.")

    for context in contexts:
        if context['name'] == context_name:
            manager_config['current_context'] = context_name  # pylint: disable=pointless-statement
            update_manager_config(manager_config)
            click.echo(f'Current context set to {context_name}.')
            return

    raise click.ClickException(
        f"{context_name} does not exist as a context at {API_SERVER_CONFIG_PATH}."
    )


def show_loading(stop_event):
    """ Show a loading spinner. """
    spinner = tqdm(total=100,
                   bar_format="{l_bar}{bar}",
                   colour="green",
                   ncols=75)
    while not stop_event.is_set():
        spinner.update(1)
        if spinner.n >= 100:
            spinner.n = 0
        time.sleep(0.05)
    spinner.close()


def get_table_str(table_type, *args, **kwargs):
    """Capture the printed table as a string."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        output_str = print_table(table_type, *args, **kwargs)
    return f"\n{output_str}\r"


def get_oldest_cluster_age(cluster_list):
    """
    Get the creation timestamp of the oldest cluster.
    """
    oldest_creation_timestamp = ""
    for cluster in cluster_list:
        if oldest_creation_timestamp == "" or \
           cluster.metadata.creation_timestamp < oldest_creation_timestamp:
            oldest_creation_timestamp = cluster.metadata.creation_timestamp
    return oldest_creation_timestamp


def calculate_total_resources(cluster_list):
    """Calculate the total and available resources for READY clusters."""
    total_resources = {}
    available_resources = {}
    for cluster in cluster_list:
        if cluster.status.status == ClusterStatusEnum.READY.value:
            total_resources.update(cluster.status.capacity)
            available_resources.update(cluster.status.allocatable_capacity)
    return total_resources, available_resources


def display_total_resources(total_resources, available_resources):
    """Display the total and available resources for READY clusters."""
    click.echo(f"{Fore.BLUE}{Style.BRIGHT}Resources{Style.RESET_ALL}")
    for resource in total_resources:
        total = total_resources[resource]
        available = available_resources.get(resource, 0)
        click.echo(f"{resource}: {available}/{total}")


def display_running_jobs(job_list):
    """Display the jobs"""
    running_jobs = [
        job for job in job_list.objects
        if job.status.conditions[-1]["type"] == JobStatusEnum.ACTIVE.value
    ]
    running_jobs_sorted = sorted(
        running_jobs,
        key=lambda job: job.metadata.creation_timestamp,
        reverse=True)

    click.echo(f"\n{Fore.BLUE}{Style.BRIGHT}Jobs{Style.RESET_ALL}", nl=False)
    print_table('job', JobList(objects=running_jobs_sorted))
