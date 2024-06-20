"""
Represents the compatibility layer over Kubernetes native API.
"""
import asyncio
import logging
import os
import time
import uuid
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple, TypedDict

import yaml
from fastapi import WebSocket
from jinja2 import Environment, FileSystemLoader, select_autoescape
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from kubernetes.stream import stream
from rapidfuzz import process

from skyshift import utils
from skyshift.cluster_manager.manager import Manager
from skyshift.globals import CLUSTER_TIMEOUT
from skyshift.templates import (AcceleratorEnum, ClusterStatus,
                               ClusterStatusEnum, EndpointObject, Endpoints,
                               Job, ResourceEnum, RestartPolicyEnum, Service,
                               TaskStatusEnum)
from skyshift.templates.job_template import ContainerStatusEnum
from skyshift.utils.utils import parse_resource_cpu, parse_resource_memory

client.rest.logger.setLevel(logging.WARNING)
logging.basicConfig(
    level=logging.INFO,
    format="%(name)s - %(asctime)s - %(levelname)s - %(message)s")


def process_pod_status(pod: client.V1Pod) -> str:
    """Processes pod status."""
    pod_status = pod.status.phase
    if pod_status == "Pending":
        if pod.spec.node_name is None:
            status = TaskStatusEnum.INIT.value
        else:
            status = TaskStatusEnum.PENDING.value
    elif pod_status == "Running":
        status = TaskStatusEnum.RUNNING.value
    elif pod_status == "Succeeded":
        status = TaskStatusEnum.COMPLETED.value
    elif pod_status in ["Failed", "Unknown"]:
        status = TaskStatusEnum.FAILED.value
    else:
        raise ValueError(f"Unknown pod status {pod_status}")
    return status


class K8ConnectionError(config.config_exception.ConfigException):
    """Raised when there is an error connecting to the Kubernetes cluster."""


class KubernetesManager(Manager):  # pylint: disable=too-many-instance-attributes
    """Kubernetes compatability set for Sky Manager."""

    def __init__(self,
                 name: str,
                 config_path: str = '~/.kube/config',
                 logger: Optional[logging.Logger] = None):
        super().__init__(name)
        self.cluster_name = utils.sanitize_cluster_name(name)
        self.logger = logger
        if not self.logger:
            self.logger = logging.getLogger(f"[{name} - K8 Manager]")
        try:
            config.load_kube_config(config_file=config_path)
        except config.config_exception.ConfigException as error:
            raise K8ConnectionError(
                "Could not connect to Kubernetes cluster "
                f"{self.cluster_name}, check kubeconfig.") from error
        all_contexts = config.list_kube_config_contexts(
            config_file=config_path)[0]
        self.context = None
        self.context_name = None
        for context in all_contexts:
            context["name"] = utils.sanitize_cluster_name(context["name"])
            if context["name"] == self.cluster_name:
                self.context = context
                self.context_name = context["name"]
                break
        assert (self.context is not None
                ), f"Could not find context {self.cluster_name} in kubeconfig."
        self.context_name = utils.unsanitize_cluster_name(self.context_name)
        self.user = self.context["context"]["user"]
        self.namespace = self.context["context"].get("namespace", "default")
        # If Kubeneretes context is identified, create Kubernetes client.
        api_client = config.new_client_from_config(context=self.context_name)
        self.core_v1 = client.CoreV1Api(api_client=api_client)
        self.apps_v1 = client.AppsV1Api(api_client=api_client)
        self.discovery_v1 = client.DiscoveryV1Api(api_client=api_client)
        # Maps node name to accelerator type.
        # Assumes each node has at most one accelerator type.
        self.accelerator_types: Dict[str, str] = {}

    async def execute_command(  # pylint: disable=too-many-arguments
            self, websocket: WebSocket, task: str, container: str, tty: bool,
            command: List[str]):
        """
        Starts a TTY session for executing commands in a container within a pod.

        This method is designed for interactive command execution, similar to SSH.
        It reads user input from stdin and sends it to the container's shell, while
        also streaming the container's stdout and stderr back to the user.

        Parameters:
        - websocket (WebSocket): The WebSocket connection to the client.
        - task (str): The name of the pod where the command will be executed.
        - container (str): The name of the container inside the pod.
        - command (List[str]): The command to execute, passed as a list of strings.
                               An empty list or None defaults to ['/bin/sh'].
        - tty (bool): If True, stdin is opened for interactive sessions.
        """
        exec_command = ['/bin/sh'] if not command else command
        try:
            if not tty:
                await websocket.send_text(
                    f"The command will be executed in the container {container} and task {task}. \n"
                )
            resp = stream(self.core_v1.connect_get_namespaced_pod_exec,
                          task,
                          self.namespace,
                          command=exec_command,
                          container=container,
                          stderr=True,
                          stdin=tty,
                          stdout=True,
                          tty=tty,
                          _preload_content=False)
        except ApiException as error:
            await websocket.send_text(f"Error connecting to pod: {error}")
            await websocket.close()
            return

        # Read from stdin and write to the container
        async def _read_stdin():
            while True:
                event = await websocket.receive()
                if event['type'] == 'websocket.receive':
                    data = event['text']
                    resp.write_stdin(data)
                elif event['type'] == 'websocket.disconnect':
                    print(f"Client disconnected with code: {event['code']}")
                    break  # Exit the loop to end the coroutine

        # Read from the container and write to remote client websocket
        async def _write_stdout_stderr():
            while resp.is_open():
                if resp.peek_stdout():
                    data = resp.read_stdout()
                    await websocket.send_text(data)
                if resp.peek_stderr():
                    data = resp.read_stderr()
                    await websocket.send_text(data)
                await asyncio.sleep(0.1)  # Prevent tight loop
            if tty:
                await websocket.close()

        write_task = asyncio.create_task(_write_stdout_stderr())
        if tty:
            read_task = asyncio.create_task(_read_stdin())
            await asyncio.gather(read_task, write_task)
        else:
            await write_task

    def get_accelerator_types(self) -> Dict[str, List[str]]:
        """Fetches accelerator types for each node."""
        accelerator_types = defaultdict(list)
        nodes = self._fetch_node_list()

        for node in nodes:
            node_name = node.metadata.name
            for label in node.metadata.labels:
                if utils.is_accelerator_label(label):
                    accelerator_types[node.metadata.labels.get(label,"")]\
                        .append(node_name)
                    break

        return accelerator_types

    def get_cluster_status(self):
        """
        Returns the current status of a Kubernetes cluster with a timeout on the list_node call.
        """
        try:
            self.core_v1.list_node(_request_timeout=CLUSTER_TIMEOUT)
            return ClusterStatus(
                status=ClusterStatusEnum.READY.value,
                capacity=self.cluster_resources,
                allocatable_capacity=self.allocatable_resources,
            )
        except config.ConfigException:
            # If there's a configuration issue, it might mean the cluster is not set up yet
            return ClusterStatus(
                status=ClusterStatusEnum.INIT.value,
                capacity=self.cluster_resources,
                allocatable_capacity=self.allocatable_resources,
            )
        except ApiException as error:
            # Handle cases where the Kubernetes API itself returns an error
            self.logger.error("API Exception: %s", error)
            return ClusterStatus(
                status=ClusterStatusEnum.ERROR.value,
                capacity=self.cluster_resources,
                allocatable_capacity=self.allocatable_resources,
            )
        except Exception as error:  # pylint: disable=broad-except
            # Catch-all for any other exception, which likely indicates an ERROR state
            self.logger.error("Unexpected error: %s", error)
            return ClusterStatus(
                status=ClusterStatusEnum.ERROR.value,
                capacity=self.cluster_resources,
                allocatable_capacity=self.allocatable_resources,
            )

    def _fetch_node_list(self) -> List[client.V1Node]:
        """Fetches the list of nodes in the cluster."""
        limit = None
        continue_token = ""
        nodes, _, _ = self.core_v1.list_node_with_http_info(
            limit=limit,
            _continue=continue_token,
            _request_timeout=CLUSTER_TIMEOUT)
        return nodes.items

    def process_resources(
            self, nodes: List[client.V1Node]
    ) -> Tuple[Dict[str, Dict[str, float]], str]:
        """Gets allocatable resources in this cluster."""

        if not nodes:
            nodes = self._fetch_node_list()

        available_resources = {}
        gpu_type = ResourceEnum.GPU.value
        for node in nodes:
            name = node.metadata.name
            node_disk = parse_resource_memory(
                node.status.allocatable.get("ephemeral-storage", "0"))
            node_cpu = parse_resource_cpu(
                node.status.allocatable.get("cpu", "0"))
            node_memory = parse_resource_memory(
                node.status.allocatable.get("memory", "0"))
            node_gpu = 0
            for allocatable in node.status.allocatable:
                if utils.is_accelerator_label(allocatable):
                    node_gpu = int(node.status.allocatable.get(allocatable, 0))
                    break

            for label in node.metadata.labels.keys():
                if utils.is_accelerator_label(label):
                    gpu_type = node.metadata.labels[label]
                    break  # Only consider the first accelerator as we only supports one accelerator type per node.
            available_resources[name] = {
                ResourceEnum.CPU.value: node_cpu,
                ResourceEnum.MEMORY.value: node_memory,  # MB
                ResourceEnum.DISK.value: node_disk,  # MB
                gpu_type: node_gpu,
            }
        return available_resources, gpu_type

    @property
    def cluster_resources(self):
        """Gets total cluster resources for each node."""
        nodes = self._fetch_node_list()

        # Initialize a dictionary to store available resources per node
        cluster_resources, _ = self.process_resources(nodes)

        return utils.fuzzy_map_gpu(cluster_resources)

    @property
    def allocatable_resources(self) -> Dict[str, Dict[str, float]]:
        """Get allocatable resources per node."""
        # Get the nodes and running pods
        limit = None
        continue_token = ""
        nodes = self._fetch_node_list()

        # Initialize a dictionary to store available resources per node
        available_resources, gpu_type = self.process_resources(nodes)

        pods, _, _ = self.core_v1.list_pod_for_all_namespaces_with_http_info(
            limit=limit, _continue=continue_token)
        pods = pods.items

        for pod in pods:
            if pod.spec.node_name:
                node_name = pod.spec.node_name
                assert node_name in available_resources.keys(), (
                    f"Node {node_name} "
                    "not found in cluster resources.")
                for container in pod.spec.containers:
                    if container.resources.requests:
                        available_resources[node_name][
                            ResourceEnum.CPU.value] -= parse_resource_cpu(
                                container.resources.requests.get("cpu", "0m"))
                        available_resources[node_name][
                            ResourceEnum.MEMORY.
                            value] -= parse_resource_memory(
                                container.resources.requests.get(
                                    "memory", "0Mi"))
                        available_resources[node_name][
                            ResourceEnum.DISK.value] -= parse_resource_memory(
                                container.resources.requests.get(
                                    "ephemeral-storage", "0Ki"))
                        available_resources[node_name][gpu_type] -= int(
                            container.resources.requests.get(
                                "nvidia.com/gpu", 0))

        return utils.fuzzy_map_gpu(available_resources)

    def submit_job(self, job: Job) -> Dict[str, Any]:
        """
        Submit a job to the cluster, represented as a group of pods.

        This method is idempotent. If the job has already been
        submitted, it does nothing.

        Args:
            job: Job object containing the YAML file.
        """
        # List all the pods in the namespace with the given label.
        job_name = job.get_name()

        # Check if the job has already been submitted.
        label_selector = f"manager=sky_manager,sky_job_id={job_name}"
        matching_pods = self.core_v1.list_namespaced_pod(
            self.namespace, label_selector=label_selector)
        matching_deployments = self.apps_v1.list_namespaced_deployment(
            self.namespace, label_selector=label_selector)
        if matching_pods.items or matching_deployments.items:
            # Job has already been submitted.
            if matching_pods.items:
                first_object = matching_pods.items[0]
            else:
                first_object = matching_deployments.items[0]
            k8_job_name = first_object.metadata.name
            split_str_ids = k8_job_name.split("-")[:2]
            k8_job_name = f"{split_str_ids[0]}-{split_str_ids[1]}"
            return {"manager_job_id": k8_job_name}

        k8_job_name = f"{job_name}-{uuid.uuid4().hex[:8]}"
        api_responses = []
        if job.spec.restart_policy == RestartPolicyEnum.ALWAYS.value:
            deploy_dict = self._convert_to_deployment_yaml(job, k8_job_name)
            response = self.apps_v1.create_namespaced_deployment(
                namespace=self.namespace, body=deploy_dict)
            api_responses.append(response)
        else:
            # Unique job name to prevent job name collisions.
            # This implicitly creates a stateful set.
            pod_dicts = self._convert_to_pod_yaml(job, k8_job_name)
            for pod_dict in pod_dicts:
                api_responses.append(
                    self.core_v1.create_namespaced_pod(
                        namespace=self.namespace, body=pod_dict))
        return {
            "manager_job_id": k8_job_name,
            "api_responses": api_responses,
        }

    def delete_job(self, job: Job) -> None:
        # List all the pods in the namespace with the given label
        if job.spec.restart_policy == RestartPolicyEnum.ALWAYS.value:
            # Delete the deployment
            self.apps_v1.delete_namespaced_deployment(
                name=job.status.job_ids[self.cluster_name],
                namespace=self.namespace)
        else:
            label_selector = f"manager=sky_manager,sky_job_id={job.get_name()}"
            pods = self.core_v1.list_namespaced_pod(
                self.namespace, label_selector=label_selector)
            # Loop through the found pods and delete them
            for pod in pods.items:
                self.core_v1.delete_namespaced_pod(name=pod.metadata.name,
                                                   namespace=self.namespace)

    def _convert_to_deployment_yaml(self, job: Job, job_name: Optional[str]):  # pylint: disable=too-many-locals
        """
        Serves as a compatibility layer to generate Deployment yamls from
        Sky Manager's job specifciations.

        Args:
            job: Generic Job object.
        """
        dir_path = os.path.dirname(os.path.realpath(__file__))
        jinja_env = Environment(
            loader=FileSystemLoader(os.path.abspath(dir_path)),
            autoescape=select_autoescape(),
        )
        deployment_jinja_template = jinja_env.get_template("k8_deployment.j2")
        replicas = sum(job.status.replica_status[self.cluster_name].values())
        node_set = []
        gpus = job.spec.resources.get(ResourceEnum.GPU.value, 0)
        accelerator_values = [m.value for m in AcceleratorEnum]
        if gpus == 0:
            job_resource_dict = {
                k: v
                for k, v in job.spec.resources.items()
                if k in accelerator_values
            }
            if len(job_resource_dict) != 0:
                assert (len(job_resource_dict) == 1
                        ), "Job can only specify one accelerator type."
                accelerator_type = list(job_resource_dict.keys())[0]
                gpus = job_resource_dict[accelerator_type]
                cluster_acc_types = self.get_accelerator_types()
                available_accelerators = list(cluster_acc_types.keys())
                best_match = process.extractOne(
                    accelerator_type, available_accelerators,
                    score_cutoff=40)  # Minimum score to match T4
                if not best_match:
                    raise ValueError(
                        f"Accelerator type {accelerator_type} not found in cluster."
                    )
                node_set = cluster_acc_types[best_match[0]]

        deployment_dict = {
            "deployment_name": job_name,
            "cluster_name": utils.unsanitize_cluster_name(self.cluster_name),
            "sky_job_id": job.get_name(),
            "sky_namespace": job.get_namespace(),
            "restart_policy": job.spec.restart_policy,
            "image": job.spec.image,
            "labels": job.metadata.labels,
            "replicas": replicas,
            "env_vars": job.spec.envs,
            "ports": job.spec.ports,
            "run": job.spec.run,
            "cpu": job.spec.resources.get(ResourceEnum.CPU.value, 0),
            "memory": job.spec.resources.get(ResourceEnum.MEMORY.value, 0),
            "gpu": gpus,
            "node_set": node_set,
        }
        deployment_jinja = deployment_jinja_template.render(deployment_dict)
        deployment_yaml = yaml.safe_load(deployment_jinja)
        return deployment_yaml

    def _convert_to_pod_yaml(self, job: Job, job_name: Optional[str] = None):  # pylint: disable=too-many-locals
        """
        Serves as a compatibility layer to generate Pod yamls from
        Sky Manager's job specifciations.

        Args:
            job: Generic Job object.
        """
        dir_path = os.path.dirname(os.path.realpath(__file__))
        replicas = sum(job.status.replica_status[self.cluster_name].values())
        jinja_env = Environment(
            loader=FileSystemLoader(os.path.abspath(dir_path)),
            autoescape=select_autoescape(),
        )
        pod_jinja_template = jinja_env.get_template("k8_pod.j2")
        pod_dicts = []
        node_set = []

        # Accelerator type for job. (Assumption: Job can only specify one accelerator type).
        gpus = job.spec.resources.get(ResourceEnum.GPU.value, 0)
        accelerator_values = [m.value for m in AcceleratorEnum]
        if gpus == 0:
            job_resource_dict = {
                k: v
                for k, v in job.spec.resources.items()
                if k in accelerator_values
            }
            if len(job_resource_dict) != 0:
                assert (len(job_resource_dict) == 1
                        ), "Job can only specify one accelerator type."
                accelerator_type = list(job_resource_dict.keys())[0]
                gpus = job_resource_dict[accelerator_type]
                cluster_acc_types = self.get_accelerator_types()
                available_accelerators = list(cluster_acc_types.keys())
                best_match = process.extractOne(
                    accelerator_type, available_accelerators,
                    score_cutoff=40)  # Minimum score to match T4
                if not best_match:
                    raise ValueError(
                        f"Accelerator type {accelerator_type} not found in cluster."
                    )
                node_set = cluster_acc_types[best_match[0]]

        for rank_id in range(replicas):
            jinja_dict = {
                "pod_name": f"{job_name}-{rank_id}",
                "cluster_name":
                utils.unsanitize_cluster_name(self.cluster_name),
                "sky_job_id": job.get_name(),
                "sky_namespace": job.get_namespace(),
                "restart_policy": job.spec.restart_policy,
                "image": job.spec.image,
                "labels": job.metadata.labels,
                "pod_rank": rank_id,
                "env_vars": job.spec.envs,
                "ports": job.spec.ports,
                "run": job.spec.run,
                "cpu": job.spec.resources.get(ResourceEnum.CPU.value, 0),
                "memory": job.spec.resources.get(ResourceEnum.MEMORY.value, 0),
                "gpu": gpus,
                "node_set": node_set,
            }
            pod_dict = pod_jinja_template.render(jinja_dict)
            pod_dict = yaml.safe_load(pod_dict)
            pod_dicts.append(pod_dict)
        return pod_dicts

    def get_pods_with_selector(self, label_selector: Dict[str, str]):
        """Gets all pods with the given label selector."""
        # label_selector['manager'] = 'sky_manager'
        label_selector_str = ",".join(
            [f"{k}={v}" for k, v in label_selector.items()])
        return self.core_v1.list_namespaced_pod(
            self.namespace, label_selector=label_selector_str)

    def get_jobs_status(self) -> Dict[str, Dict[str, Dict[str, str]]]:
        """Gets the jobs tasks status. (Map from job name to task mapped to status)"""
        # @TODO(mluo): Minimize K8 API calls by doing a List and Watch over
        # pods.
        # Filter jobs that that are submitted by Sky Manager.
        sky_manager_pods = self.core_v1.list_namespaced_pod(
            self.namespace, label_selector="manager=sky_manager")
        jobs_dict: Dict[str, Dict[str, Dict[str, str]]] = {
            "tasks": {},
            "containers": {}
        }
        for pod in sky_manager_pods.items:
            sky_job_name = pod.metadata.labels["sky_job_id"]
            pod_status = process_pod_status(pod)
            if sky_job_name not in jobs_dict["tasks"]:
                jobs_dict["tasks"][sky_job_name] = {}
            jobs_dict["tasks"][sky_job_name][pod.metadata.name] = pod_status
            # To prevent crashes when a pod is scheduled but doesn't have containers running.
            if not pod.status.container_statuses:
                continue
            for container_status in pod.status.container_statuses:
                state: str = ContainerStatusEnum.UNKNOWN.value  # Default state
                if container_status.state.running is not None:
                    state = ContainerStatusEnum.RUNNING.value
                elif container_status.state.waiting is not None:
                    state = ContainerStatusEnum.WAITING.value
                elif container_status.state.terminated is not None:
                    state = ContainerStatusEnum.TERMINATED.value
                if pod.metadata.name not in jobs_dict["containers"]:
                    jobs_dict["containers"][pod.metadata.name] = {
                        container_status.name: state
                    }
                else:
                    jobs_dict["containers"][pod.metadata.name][
                        container_status.name] = state

        return jobs_dict

    def get_service_status(self) -> Dict[str, Dict[str, str]]:
        """Gets the jobs state. (Map from job name to status)"""
        # @TODO(mluo): Minimize K8 API calls by doing a List and Watch over
        # K8 services.
        sky_svcs = self.core_v1.list_namespaced_service(
            self.namespace,
            label_selector="manager=sky_manager,primary_service=skyservice")

        svc_dict: Dict[str, Dict[str, str]] = {}
        for svc in sky_svcs.items:
            svc_name = svc.metadata.name
            if svc_name not in svc_dict:
                svc_dict[svc_name] = {}
            # Inject clusterIP and Loadbalanacer external ip
            svc_dict[svc_name]["clusterIP"] = svc.spec.cluster_ip
            # Check if loabalancer ip exists
            if svc.status.load_balancer.ingress:
                svc_dict[svc_name][
                    "externalIP"] = svc.status.load_balancer.ingress[0].ip
        return svc_dict

    def get_job_logs(self, job: Job) -> List[str]:
        """Gets logs for a given job."""
        # Find pods associated with the Job
        pods = job.status.task_status[self.cluster_name]
        running_pods = [
            pod_name for pod_name, status in pods.items()
            if status == TaskStatusEnum.RUNNING.value
        ]
        # Fetch and print logs from each Pod
        logs = []
        for pod in running_pods:
            log = self.core_v1.read_namespaced_pod_log(pod, self.namespace)
            logs.append(log)
        return logs

    def create_or_update_service(self, service: Service) -> None:
        """Creates or updates service on K8 cluster."""
        dir_path = os.path.dirname(os.path.realpath(__file__))
        jinja_env = Environment(
            loader=FileSystemLoader(os.path.abspath(dir_path)),
            autoescape=select_autoescape(),
        )
        service_jinja_template = jinja_env.get_template("k8_service.j2")
        if service.spec.primary_cluster == self.cluster_name:
            service_type = service.spec.type
            primary_service = "skyservice"
        else:
            service_type = "ClusterIP"
            primary_service = "bye"
        service_dict = {
            "name": f"{service.get_name()}",
            "type": service_type,
            "primary_service": primary_service,
            "sky_namespace": service.get_namespace(),
            "selector": service.spec.selector,
            "ports": service.spec.ports,
        }
        service_jinja = service_jinja_template.render(service_dict)
        service_yaml = yaml.safe_load(service_jinja)

        try:
            self.core_v1.create_namespaced_service(namespace=self.namespace,
                                                   body=service_yaml)
        except client.exceptions.ApiException as error:
            if error.status == 409:  # Conflict, service already exists
                # Update service
                self.core_v1.patch_namespaced_service(name=service.get_name(),
                                                      namespace=self.namespace,
                                                      body=service_yaml)
            else:
                raise error

    def delete_service(self, service: Service) -> None:
        """Deletes a service from Kubernetes cluster."""
        try:
            self.core_v1.delete_namespaced_service(name=service.get_name(),
                                                   namespace=self.namespace)
        except client.exceptions.ApiException as error:
            if error.status != 404:
                raise error

    def create_endpoint_slice(  # pylint: disable=too-many-locals, too-many-branches
            self, name: str, cluster_name, endpoint: EndpointObject):
        """Creates/updates an endpoint slice."""
        dir_path = os.path.dirname(os.path.realpath(__file__))
        jinja_env = Environment(loader=FileSystemLoader(
            os.path.abspath(dir_path)),
                                autoescape=select_autoescape())
        endpoint_template = jinja_env.get_template('k8_endpointslice.j2')

        class EndpointDict(TypedDict):
            """Endpoint dictionary to be passed into Jinja template."""
            addresses: List[str]
            ports: List[int]
            object_name: str
            name: str

        endpoint_dict: EndpointDict = {
            "object_name": "",
            "name": name,
            "addresses": [],
            "ports": [],
        }

        while True:
            try:
                # Get the endpoints object.
                exposed_k8_endpoints = self.core_v1.read_namespaced_endpoints(
                    name=f'{name}-{cluster_name}', namespace=self.namespace)
                break
            except client.exceptions.ApiException as error:
                if error.status == 404:
                    # Endpoints object does not exist yet.
                    time.sleep(0.1)
                    continue
        for _ in range(endpoint.num_endpoints):
            subsets = exposed_k8_endpoints.subsets
            assert len(subsets) <= 1, "Only one subset is supported."
            subset = subsets[0]
            # Loop through ports in each subset
            ports = [p.port for p in subset.ports]
            # Loop through addresses in each subset
            for address in subset.addresses:
                # Get the pod IP
                pod_ip = address.ip
                endpoint_dict['addresses'].append(pod_ip)
            break

        endpoint_dict['ports'].extend(ports)
        endpoint_dict['object_name'] = f'{name}-{cluster_name}'
        if not endpoint_dict['addresses']:
            return False

        endpoint_jinja = endpoint_template.render(endpoint_dict)
        print(endpoint_jinja)
        endpoint_yaml = yaml.safe_load(endpoint_jinja)
        try:
            # Create an EndpointSlice
            self.discovery_v1.create_namespaced_endpoint_slice(
                namespace=self.namespace, body=endpoint_yaml)
        except client.rest.ApiException as error:
            if error.status == 409:
                # EndpointSlice already exists, update it
                logging.info("Updating endpointslice since it already exists")
                self.discovery_v1.replace_namespaced_endpoint_slice(
                    name=endpoint_dict['object_name'],
                    namespace=self.namespace,
                    body=endpoint_yaml)
            else:
                raise error

    def delete_endpoint_slice(self, endpoints: Endpoints):
        """Deletes an endpoint slice object from K8 cluster."""
        name = endpoints.get_name()
        # Get all endpoints under label
        label_selector = f"manager=sky-manager,kubernetes.io/service-name={name}"
        endpoints_list = self.discovery_v1.list_namespaced_endpoint_slice(
            namespace=self.namespace, label_selector=label_selector)
        for e_slice in endpoints_list.items:
            try:
                self.discovery_v1.delete_namespaced_endpoint_slice(
                    name=e_slice.metadata.name, namespace=self.namespace)
            except client.exceptions.ApiException as error:
                if error.status == 404:
                    # Endpoint slice does not exist.
                    pass
                else:
                    raise error
