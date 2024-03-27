"""
Represents the comptability layer over Kubernetes native API.
"""
import asyncio
import logging
import os
import re
import sys
import termios
import time
import tty
import uuid
from threading import Thread
from typing import Any, Dict, List, Optional, TypedDict
from kubernetes.client.exceptions import ApiException

from fastapi import WebSocket
import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape
from kubernetes import client, config
from kubernetes.stream import stream

from skyflow.cluster_manager.manager import Manager
from skyflow.templates import (AcceleratorEnum, ClusterStatus,
                               ClusterStatusEnum, EndpointObject, Endpoints,
                               Job, ResourceEnum, RestartPolicyEnum, Service,
                               TaskStatusEnum)

client.rest.logger.setLevel(logging.WARNING)
logging.basicConfig(
    level=logging.INFO,
    format="%(name)s - %(asctime)s - %(levelname)s - %(message)s")


def parse_resource_cpu(resource_str):
    """Parse CPU string to cpu count."""
    unit_map = {"m": 1e-3, "K": 1e3}
    value = re.search(r"\d+", resource_str).group()
    unit = resource_str[len(value):]
    return float(value) * unit_map.get(unit, 1)


def parse_resource_memory(resource_str):
    """Parse resource string to megabytes."""
    unit_map = {"Ki": 2**10, "Mi": 2**20, "Gi": 2**30, "Ti": 2**40}
    value = re.search(r"\d+", resource_str).group()
    unit = resource_str[len(value):]
    return float(value) * unit_map.get(unit, 1) / (2**20)


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

    def __init__(self, name: str, config_path: str = '~/.kube/config'):
        super().__init__(name)
        self.logger = logging.getLogger(f"[{self.cluster_name} - K8 Manager]")

        try:
            config.load_kube_config(config_file=config_path)
        except config.config_exception.ConfigException as error:
            raise K8ConnectionError(
                "Could not connect to Kubernetes cluster "
                f"{self.cluster_name}, check kubeconfig.") from error
        all_contexts = config.list_kube_config_contexts(
            config_file=config_path)[0]
        self.context = None
        for context in all_contexts:
            if context["name"] == self.cluster_name:
                self.context = context
                break
        assert (self.context is not None
                ), f"Could not find context {self.cluster_name} in kubeconfig."

        self.user = self.context["context"]["user"]
        self.namespace = self.context["context"].get("namespace", "default")
        # If Kubeneretes context is identified, create Kubernetes client.
        self.core_v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()
        self.discovery_v1 = client.DiscoveryV1Api()
        # Maps node name to accelerator type.
        # Assumes each node has at most one accelerator type.
        self.accelerator_types: Dict[str, str] = {}

    def retrieve_tasks_from_job(self, job: Job) -> List[client.V1Pod]:
        """
        Retrieves a list of pods (tasks) associated with a given job based on specific labels.

        This method queries the Kubernetes API to find pods that match the labels indicating they are part
        of the specified job. It constructs a label selector string using the job's name to identify these pods.
        The search is scoped to the namespace associated with the instance of this class.

        Args:
            job (Job): The job object, which must provide a method `get_name()` that returns the\
                  job's name used for label matching.

        Returns:
            List[client.V1Pod]: A list of V1Pod objects representing the pods found for the job.\
                  Returns an empty list if no matching pods are found.

        """
        label_selector = f"manager=sky_manager,sky_job_id={job.get_name()}"
        return self.core_v1.list_namespaced_pod(
            self.namespace, label_selector=label_selector).items or []
    
    def retrieve_containers_from_job(self, job: Job, task_name: str = None) -> List[str]:
        """
        Retrieves the names of containers running within the pods associated with a specific job, \
            optionally filtered by a single task name.

        This method queries the Kubernetes API for pods tied to the job specified by `job` and, if provided,\
              further narrows down the pods to the one matching `task_name`. It then collects and returns \
                the names of all containers found within these pods.

        Args:
            job (Job): The job object, expected to have a method `get_name()` that returns the unique identifier of \
                the job for label matching.
            task_name (str, optional): The name of a specific pod (task) to filter the search. If None, containers from all \
                pods under the job will be listed.

        Returns:
            List[str]: A list of container names found within the specified job's pods. Returns an empty list if \
                no matching containers are found.
        """
        containers = []
        label_selector = f"manager=sky_manager,sky_job_id={job.get_name()}"
        pods = self.core_v1.list_namespaced_pod(self.namespace, label_selector=label_selector).items
        
        # Iterate over each pod to collect container names
        for pod in pods:
            if task_name and pod.metadata.name != task_name:
                continue
            for container in pod.spec.containers:
                containers.append(container.name)
        
        return containers

    async def start_tty_session(self, websocket: WebSocket, pod: str, container: str, command: List[str]):
        """
        Starts a TTY session for executing commands in a container within a pod.

        This method is designed for interactive command execution, similar to SSH.
        It reads user input from stdin and sends it to the container's shell, while
        also streaming the container's stdout and stderr back to the user.

        Parameters:
        - websocket (WebSocket): The WebSocket connection to the client.
        - pod (str): The name of the pod where the command will be executed.
        - container (str): The name of the container inside the pod.
        - command (List[str]): The command to execute, passed as a list of strings.
                               An empty list or None defaults to ['/bin/sh'].
        - stdin (bool): If True, stdin is opened for interactive sessions.
        """
        exec_command = ['/bin/sh'] if not command else command
        try:
            resp = stream(self.core_v1.connect_get_namespaced_pod_exec,
                        pod,
                        self.namespace,
                        command=exec_command,
                        container=container,
                        stderr=True,
                        stdin=True,
                        stdout=True,
                        tty=True,
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
            await websocket.close()

        read_task = asyncio.create_task(_read_stdin())
        write_task = asyncio.create_task(_write_stdout_stderr())

        await asyncio.gather(read_task, write_task)

    def execute_command(
            self, task: str, container: str, command: List[str], quiet: bool) -> str:
        """
        Executes a specified command in a container within a task.

        Parameters:
        - task (str): The name of the task where the command will be executed.
        - container (str): The name of the container inside the task.
        - command (List[str]): The command to execute, passed as a list of strings.
        - stdin (bool): If True, stdin is opened for the command or session.
        - tty_enabled (bool): If True, opens a TTY session. If False, executes the command \
            non-interactively.
        - quiet (bool): If True, suppresses output for non-TTY command execution.
        """
        try:
            resp = stream(self.core_v1.connect_get_namespaced_pod_exec,
                          task,
                          self.namespace,
                          command=['/bin/sh', '-c', ' '.join(command)],
                          container=container,
                          stderr=True,
                          stdin=False,
                          stdout=not quiet,
                          tty=False,
                          _preload_content=False)
            output = ""
            while resp.is_open():
                resp.update(timeout=1)
                if resp.peek_stdout():
                    output += resp.read_stdout()
                if resp.peek_stderr():
                    output += resp.read_stderr()
            resp.close()
            return output
        except Exception as error:
            self.logger.error("Error during command execution: %s", error)
            raise

    def get_accelerator_types(self) -> Dict[str, str]:
        """Fetches accelerator types for each node."""
        # For now overfit to GKE cluster. TODO(mluo): Replace with a more general solution.
        accelerator_labels = [
            "nvidia.com/gpu.product", "cloud.google.com/gke-accelerator"
        ]
        accelerator_types = {}
        node_list = self.core_v1.list_node()
        for node in node_list.items:
            node_name = node.metadata.name
            # Fetch type from list of labels. None otherwise.
            for label in accelerator_labels:
                node_accelerator_type = node.metadata.labels.get(label, None)
                if node_accelerator_type:
                    break
            if node_accelerator_type is None:
                continue
            node_accelerator_type = node_accelerator_type.split(
                "-")[-1].upper()
            accelerator_types[node_name] = node_accelerator_type
        return accelerator_types

    def get_cluster_status(self):
        """
        Returns the current status of a Kubernetes cluster.
        """
        try:
            self.core_v1.list_node()
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
        except Exception as error:  # pylint: disable=broad-except
            # Catch-all for any other exception, which likely indicates an ERROR state
            print(f"Unexpected error: {error}")
            return ClusterStatus(
                status=ClusterStatusEnum.ERROR.value,
                capacity=self.cluster_resources,
                allocatable_capacity=self.allocatable_resources,
            )

    def _process_gpu_resources(
            self, resources: Dict[str,
                                  Dict[str,
                                       float]]) -> Dict[str, Dict[str, float]]:
        # Refetch node accelerator types if the nodes have changed
        # (such as in cluster autoscaling or admin adds/removes nodes).
        if not self.accelerator_types or not set(
                self.accelerator_types).issubset(set(resources.keys())):
            self.accelerator_types = self.get_accelerator_types()

        for node_name, accelerator_type in self.accelerator_types.items():
            gpu_value: float = resources[node_name].pop(ResourceEnum.GPU.value)
            resources[node_name][accelerator_type] = gpu_value
        return resources

    @property
    def cluster_resources(self):
        """Gets total cluster resources for each node."""
        limit = None
        continue_token = ""
        nodes, _, _ = self.core_v1.list_node_with_http_info(
            limit=limit, _continue=continue_token)
        nodes = nodes.items

        # Initialize a dictionary to store available resources per node
        cluster_resources = {}
        for node in nodes:
            name = node.metadata.name
            node_cpu = parse_resource_cpu(node.status.capacity["cpu"])
            node_memory = parse_resource_memory(node.status.capacity["memory"])
            node_gpu = int(node.status.allocatable.get("nvidia.com/gpu", 0))
            cluster_resources[name] = {
                ResourceEnum.CPU.value: node_cpu,
                ResourceEnum.MEMORY.value: node_memory,  # MB
                ResourceEnum.GPU.value: node_gpu,
            }

        return self._process_gpu_resources(cluster_resources)

    @property
    def allocatable_resources(self) -> Dict[str, Dict[str, float]]:
        """Get allocatable resources per node."""
        # Get the nodes and running pods
        limit = None
        continue_token = ""
        nodes, _, _ = self.core_v1.list_node_with_http_info(
            limit=limit, _continue=continue_token)
        nodes = nodes.items

        available_resources = {}
        for node in nodes:
            node_name = node.metadata.name
            node_cpu = parse_resource_cpu(node.status.allocatable["cpu"])
            node_memory = parse_resource_memory(
                node.status.allocatable["memory"])
            node_gpu = float(node.status.allocatable.get("nvidia.com/gpu", 0))
            available_resources[node_name] = {
                ResourceEnum.CPU.value: node_cpu,
                ResourceEnum.MEMORY.value: node_memory,
                ResourceEnum.GPU.value: node_gpu,
            }

        pods, _, _ = self.core_v1.list_pod_for_all_namespaces_with_http_info(
            limit=limit, _continue=continue_token)
        pods = pods.items

        for pod in pods:
            if pod.metadata.namespace == self.namespace and pod.spec.node_name:
                assert node_name in available_resources, (
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
                            ResourceEnum.GPU.value] -= int(
                                container.resources.requests.get(
                                    "nvidia.com/gpu", 0))
        return self._process_gpu_resources(available_resources)

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
                for node_name, acc_type in cluster_acc_types.items():
                    if acc_type == accelerator_type:
                        node_set.append(node_name)

        deployment_dict = {
            "deployment_name": job_name,
            "cluster_name": self.cluster_name,
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
                for node_name, acc_type in cluster_acc_types.items():
                    if acc_type == accelerator_type:
                        node_set.append(node_name)

        for rank_id in range(replicas):
            jinja_dict = {
                "pod_name": f"{job_name}-{rank_id}",
                "cluster_name": self.cluster_name,
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

    def get_jobs_status(self) -> Dict[str, Dict[str, int]]:
        """Gets the jobs state. (Map from job name to status)"""
        # @TODO(mluo): Minimize K8 API calls by doing a List and Watch over
        # pods.
        # Filter jobs that that are submitted by Sky Manager.
        sky_manager_pods = self.core_v1.list_namespaced_pod(
            self.namespace, label_selector="manager=sky_manager")
        jobs_dict: Dict[str, Dict[str, int]] = {}
        for pod in sky_manager_pods.items:
            sky_job_name = pod.metadata.labels["sky_job_id"]
            pod_status = process_pod_status(pod)
            if sky_job_name not in jobs_dict:
                jobs_dict[sky_job_name] = {}
            if pod_status not in jobs_dict[sky_job_name]:
                jobs_dict[sky_job_name][pod_status] = 0
            jobs_dict[sky_job_name][pod_status] += 1
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
        pods = self.core_v1.list_namespaced_pod(
            self.namespace,
            label_selector=f"manager=sky_manager,sky_job_id={job.get_name()}")
        # Fetch and print logs from each Pod
        logs = []
        for pod in pods.items:
            pod_name = pod.metadata.name
            log = self.core_v1.read_namespaced_pod_log(pod_name,
                                                       self.namespace)
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
        """Creates/updates an endpint slice."""
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
