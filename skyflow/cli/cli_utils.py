"""
Utils for Skyflow CLI.
"""
import enum
import json as json_lib
from typing import Dict, List, Optional, Union

import click
from tabulate import tabulate

from skyflow import utils
from skyflow.api_client import (ClusterAPI, EndpointsAPI, FilterPolicyAPI,
                                JobAPI, LinkAPI, NamespaceAPI, RoleAPI,
                                ServiceAPI, UserAPI)
# Import API parent class.
from skyflow.api_client.exec_api import ExecAPI
from skyflow.api_client.object_api import APIException, ObjectAPI
from skyflow.globals import DEFAULT_NAMESPACE
from skyflow.templates import (Cluster, ClusterList, FilterPolicy,
                               FilterPolicyList, Job, JobList, Link, LinkList,
                               Namespace, NamespaceList, Object, ObjectList,
                               Service, ServiceList, TaskStatusEnum)
from skyflow.utils.utils import (API_SERVER_CONFIG_PATH,
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
        raise click.ClickException(f"Failed to create {object_type}: {error}")
    if object_type != "exec":
        click.echo(f"Created {object_type} {config['metadata']['name']}.")
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
            f"Failed to create {object_type} stream: {error}")
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
        raise click.ClickException(f"Failed to get {object_type}: {error}")
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
        raise click.ClickException(f"Failed to delete {object_type}: {error}")
    click.echo(f"Deleted {object_type} {name}.")
    return api_response


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
        raise click.ClickException(f"Failed to fetch logs: {error}")


def _get_object_age(obj: Object) -> str:
    creation_str = obj.metadata.creation_timestamp
    obj_age = compute_datetime_delta(creation_str, fetch_datetime())
    return obj_age


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
        FieldEnum.NAME.value, "MANAGER", "RESOURCES", FieldEnum.STATUS.value,
        FieldEnum.AGE.value
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
            resources_str += f"{key}: {available_resources}/{resources[key]}\n"
        if not resources_str:
            resources_str = "{}"
        status = entry.get_status()
        table_data.append([name, manager_type, resources_str, status, age])

    table = tabulate(table_data, field_names, tablefmt="plain")
    click.echo(f"{table}\r")


def print_job_table(job_list: Union[JobList, Job]):  #pylint: disable=too-many-locals, too-many-branches
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
                    status,
                    age,
                ])
        else:
            table_data.append([
                name,
                "",
                f"0/{entry.spec.replicas}",
                resources_str,
                namespace,
                status,
                age,
            ])

    table = tabulate(table_data, field_names, tablefmt="plain")
    click.echo(f"{table}\r")


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
        status = entry.get_status()
        age = _get_object_age(entry)
        table_data.append([name, status, age])

    table = tabulate(table_data, field_names, tablefmt="plain")
    click.echo(f"{table}\r")


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
        status = entry.get_status()
        table_data.append([
            name, include, exclude, labels, namespace, status,
            _get_object_age(entry)
        ])

    table = tabulate(table_data, field_names, tablefmt="plain")
    click.echo(f"{table}\r")


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

    table = tabulate(table_data, field_names, tablefmt="plain")
    click.echo(f"{table}\r")


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
        status = entry.get_status()
        age = _get_object_age(entry)
        table_data.append([name, source, target, status, age])

    table = tabulate(table_data, field_names, tablefmt="plain")
    click.echo(f"{table}\r")


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

    table = tabulate(table_data, field_names, tablefmt="plain")
    click.echo(f"{table}\r")


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

    table = tabulate(table_data, field_names, tablefmt="plain")
    click.echo(f"{table}\r")


def register_user(username: str, email: str, password: str, invite: str):
    """
    Register user in API Server.
    """
    users_api: UserAPI = fetch_api_client_object("user")  #type: ignore

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
    users_api: UserAPI = fetch_api_client_object("user")  #type: ignore
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
    users_api: UserAPI = fetch_api_client_object("user")  #type: ignore
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
    users_api: UserAPI = fetch_api_client_object("user")  #type: ignore
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


def switch_context(username, namespace):
    """
    Switch local CLI active context.
    """
    manager_config = load_manager_config()

    if namespace:
        manager_config['metadata']["namespace"] = namespace
        update_manager_config(manager_config)
        click.echo(f"Updated active namespace at {API_SERVER_CONFIG_PATH}.")

    if username:
        if 'users' not in manager_config:
            raise click.ClickException(
                f"{username} does not exist as a user at {API_SERVER_CONFIG_PATH}."
            )

        for user in manager_config['users']:
            if user['name'] == username:
                manager_config['current_user'] = username
                update_manager_config(manager_config)
                click.echo(f"Updated active user at {API_SERVER_CONFIG_PATH}.")
                return

        raise click.ClickException(
            f"{username} does not exist as a user at {API_SERVER_CONFIG_PATH}."
        )
