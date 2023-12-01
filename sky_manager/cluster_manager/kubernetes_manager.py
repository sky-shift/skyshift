import logging
import re
import os
from typing import Dict, Tuple
import uuid

from jinja2 import Environment, select_autoescape, FileSystemLoader
from kubernetes import client, config
import yaml

from sky_manager.cluster_manager import Manager
from sky_manager.templates import Job, TaskStatusEnum, AcceleratorEnum, ResourceEnum

client.rest.logger.setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def parse_resource_cpu(resource_str):
    """ Parse CPU string to cpu count. """
    unit_map = {'m': 1e-3, 'K': 1e3}
    value = re.search(r'\d+', resource_str).group()
    unit = resource_str[len(value):]
    return float(value) * unit_map.get(unit, 1)


def parse_resource_memory(resource_str):
    """ Parse resource string to megabytes. """
    unit_map = {'Ki': 2**10, 'Mi': 2**20, 'Gi': 2**30, 'Ti': 2**40}
    value = re.search(r'\d+', resource_str).group()
    unit = resource_str[len(value):]
    return float(value) * unit_map.get(unit, 1) / (2**20)

class K8ConnectionError(config.config_exception.ConfigException):
    """ Raised when there is an error connecting to the Kubernetes cluster. """
    pass

# Pull based architecture
class KubernetesManager(Manager):
    """ Kubernetes compatability set for Sky Manager.
    """

    def __init__(self, name: str, namespace: str = 'default'):
        super().__init__(name)
        self.name = name
        self.namespace = namespace
        # Load kubernetes config for the given context.
        try:
            config.load_kube_config(context=self.cluster_name)
        except config.config_exception.ConfigException:
            raise K8ConnectionError(
                f"Could not connect to Kubernetes cluster {self.cluster_name}. Check your kubeconfig."
            )
        # If Kubeneretes context is identified, create Kubernetes client.
        self.core_v1 = client.CoreV1Api()
        self.accelerator_types = None
    

    def get_accelerator_types(self):
        # For now overfit to GKE cluster. TODO: Replace with a more general solution.
        accelerator_types = {}
        node_list = self.core_v1.list_node()
        for node in node_list.items:
            node_name = node.metadata.name
            node_accelerator_type = node.metadata.labels.get(
                'cloud.google.com/gke-accelerator', None)
            if node_accelerator_type is None:
                continue
            node_accelerator_type = node_accelerator_type.split('-')[-1].upper()
            accelerator_types[node_name] = node_accelerator_type
        return accelerator_types

    @property
    def cluster_resources(self):
        """ Gets total cluster resources for each node."""
        limit = None
        continue_token = ""
        nodes, _, _ = self.core_v1.list_node_with_http_info(
            limit=limit, _continue=continue_token)
        nodes = nodes.items

        # Initialize a dictionary to store available resources per node
        cluster_resources = {}
        for node in nodes:
            name = node.metadata.name
            node_cpu = parse_resource_cpu(node.status.capacity['cpu'])
            node_memory = parse_resource_memory(node.status.capacity['memory'])
            node_gpu = int(node.status.allocatable.get('nvidia.com/gpu', 0))
            cluster_resources[name] = {
                ResourceEnum.CPU.value: node_cpu,
                ResourceEnum.MEMORY.value: node_memory,  # MB
                ResourceEnum.GPU.value: node_gpu
            }

        return self._process_gpu_resources(cluster_resources)

    def _process_gpu_resources(self, resources: Dict[str, Dict[str, int]]) -> Dict[str, Dict[str, int]]:
        # Refetch node accelerator types if the nodes have changed (such as in cluster autoscaling or admin adds/removes nodes from the cluster).
        if not self.accelerator_types or not set(self.accelerator_types).issubset(set(resources.keys())):
            self.accelerator_types = self.get_accelerator_types()
        
        for node_name, accelerator_type in self.accelerator_types.items():
            resources[node_name][accelerator_type] = resources[node_name].pop(ResourceEnum.GPU.value)
        return resources

    @property
    def allocatable_resources(self) -> Dict[str, Dict[str, int]]:
        """ Get allocatable resources per node. """
        # Get the nodes and running pods
        limit = None
        continue_token = ""
        nodes, _, _ = self.core_v1.list_node_with_http_info(
            limit=limit, _continue=continue_token)
        nodes = nodes.items

        available_resources = {}
        for node in nodes:
            node_name = node.metadata.name
            node_cpu = parse_resource_cpu(node.status.allocatable['cpu'])
            node_memory = parse_resource_memory(
                node.status.allocatable['memory'])
            node_gpu = int(node.status.allocatable.get('nvidia.com/gpu', 0))
            available_resources[node_name] = {
                ResourceEnum.CPU.value: node_cpu,
                ResourceEnum.MEMORY.value: node_memory,
                ResourceEnum.GPU.value: node_gpu
            }

        pods, _, _ = self.core_v1.list_pod_for_all_namespaces_with_http_info(
            limit=limit, _continue=continue_token)
        pods = pods.items

        for pod in pods:
            # Add pending?
            if pod.status.phase in [
                    'Running',
                    'Pending',
            ] and pod.metadata.namespace == self.namespace:
                node_name = pod.spec.node_name
                if node_name is None:
                    continue
                assert node_name in available_resources, (
                    f"Node {node_name} "
                    "not found in cluster resources.")
                for container in pod.spec.containers:
                    if container.resources.requests:
                        available_resources[node_name][
                            ResourceEnum.CPU.value] -= parse_resource_cpu(
                                container.resources.requests.get('cpu', '0m'))
                        available_resources[node_name][
                            ResourceEnum.MEMORY.value] -= parse_resource_memory(
                                container.resources.requests.get(
                                    'memory', '0Mi'))
                        available_resources[node_name][ResourceEnum.GPU.value] -= int(
                            container.resources.requests.get(
                                'nvidia.com/gpu', 0))
        return self._process_gpu_resources(available_resources)

    def submit_job(self, job: Job) -> None:
        """
        Submit a job to the cluster, represented as a group of pods.

        This method is idempotent. If the job has already been submitted, it does nothing.

        Args:
            job: Job object containing the YAML file.
        """
        # List all the pods in the namespace with the given label.
        job_name = job.get_name()
        
        # Check if the job has already been submitted.
        label_selector = f'manager=sky_manager,sky_job_id={job_name}'
        matching_pods = self.core_v1.list_namespaced_pod(self.namespace, label_selector=label_selector)
        if matching_pods.items:
            # Job has already been submitted.
            rank_0_pod = matching_pods.items[0]
            k8_job_name = rank_0_pod.metadata.name
            last_hyphen_idx = k8_job_name.rfind('-')
            if last_hyphen_idx != -1:
                k8_job_name = k8_job_name[:last_hyphen_idx]
            return {
                'manager_job_id': k8_job_name
            }
        # Unique job name to prevent job name collisions.
        k8_job_name = f'{job_name}-{uuid.uuid4().hex[:8]}'
        pod_dicts = self._convert_to_pod_yaml(job, k8_job_name)
        api_responses = []
        for pod_dict in pod_dicts:
            api_responses.append(self.core_v1.create_namespaced_pod(
                namespace=self.namespace, body=pod_dict))
        return {
            'manager_job_id': k8_job_name,
            'api_responses': api_responses,
        }

    def delete_job(self, job: Job) -> None:
        # List all the pods in the namespace with the given label
        label_selector = f'manager=sky_manager,sky_job_id={job.get_name()}'
        pods = self.core_v1.list_namespaced_pod(self.namespace, label_selector=label_selector)
     
        # Loop through the found pods and delete them
        for pod in pods.items:
            self.core_v1.delete_namespaced_pod(name=pod.metadata.name, namespace=self.namespace)

    def _convert_to_pod_yaml(self, job: Job, job_name: str = None):
        """
        Serves as a compatibility layer to generate Pod yamls from
        Sky Manager's job specifciations.

        Args:
            job: Generic Job object.
        """
        dir_path = os.path.dirname(os.path.realpath(__file__))
        replicas = sum(job.status.replica_status[self.name].values())
        jinja_env = Environment(loader=FileSystemLoader(
            os.path.abspath(dir_path)),
            autoescape=select_autoescape())
        pod_jinja_template = jinja_env.get_template('k8_pod.j2')
        pod_dicts = []
        node_set = []

        # Accelerator type for job. (Assumption: Job can only specify one accelerator type).
        gpus = job.spec.resources.get(ResourceEnum.GPU.value, 0)
        accelerator_values = [m.value for m in AcceleratorEnum]
        if gpus ==0:
            job_resource_dict = {k:v for k,v in job.spec.resources.items() if k in accelerator_values}
            if len(job_resource_dict) !=0:
                assert len(job_resource_dict) == 1, "Job can only specify one accelerator type."
                accelerator_type = list(job_resource_dict.keys())[0]
                gpus = job_resource_dict[accelerator_type]
                cluster_acc_types = self.get_accelerator_types()
                for node_name, acc_type in cluster_acc_types.items():
                    if acc_type == accelerator_type:
                        node_set.append(node_name)

        for rank_id in range(replicas):
            jinja_dict = {
                'pod_name': f'{job_name}-{rank_id}',
                'cluster_name': self.cluster_name,
                'sky_job_id': job.get_name(),
                'restart_policy': 'Never',
                'image': job.spec.image,
                'pod_rank': rank_id,
                'env_vars': job.spec.envs,
                'ports': job.spec.ports,
                'run': job.spec.run,
                'cpu': job.spec.resources.get(ResourceEnum.CPU.value, 0),
                'gpu': gpus,
                'node_set': node_set,
            }
            pod_dict = pod_jinja_template.render(jinja_dict)
            print(pod_dict)
            pod_dict = yaml.safe_load(pod_dict)
            pod_dicts.append(pod_dict)
        return pod_dicts

    def get_jobs_status(self) -> Dict[str, Tuple[str, str]]:
        """ Gets the jobs state. (Map from job name to status) """
        # TODO(mluo): Minimize K8 API calls by doing a List and Watch over
        # Sky Manager pods
        # Filter jobs that that are submitted by Sky Manager.
        sky_manager_pods = self.core_v1.list_namespaced_pod(self.namespace, label_selector='manager=sky_manager')
        jobs_dict = {}
        for pod in sky_manager_pods.items:
            sky_job_name = pod.metadata.labels['sky_job_id']
            pod_status = self._process_pod_status(pod)
            if sky_job_name not in jobs_dict:
                jobs_dict[sky_job_name] = {}
            if pod_status not in jobs_dict[sky_job_name]:
                jobs_dict[sky_job_name][pod_status] = 0
            jobs_dict[sky_job_name][pod_status] += 1
        return jobs_dict

    def _process_pod_status(self, pod):
        pod_status = pod.status.phase
        status = None
        if pod_status == 'Pending':
            status = TaskStatusEnum.PENDING.value
        elif pod_status == 'Running':
            status = TaskStatusEnum.RUNNING.value
        elif pod_status == 'Succeeded':
            status = TaskStatusEnum.COMPLETED.value
        elif pod_status == 'Failed' or pod_status == 'Unknown':
            status = TaskStatusEnum.FAILED.value
        return status
