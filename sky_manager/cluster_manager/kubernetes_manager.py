import copy
from enum import Enum
import logging
import re
import os
from typing import Any, Dict, List

from jinja2 import Environment, select_autoescape, FileSystemLoader
from kubernetes import client, config
from kubernetes.client import models
import yaml

from sky_manager.cluster_manager import Manager
from sky_manager.templates.job_template import Job, JobStatus, JobStatusEnum

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
                f"Could not connect to Kubernetes cluster {self.cluster_name}."
            )

        # If Kubeneretes context is identifies, create Kubernetes client.
        self.core_v1 = client.CoreV1Api()
        self.batch_v1 = client.BatchV1Api()

        self._cluster_state = {}
        self._job_state = {}

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
            node_gpu = int(node.status.capacity.get('nvidia.com/gpu', 0))
            cluster_resources[name] = {
                'cpu': node_cpu,
                'memory': node_memory,  # MB
                'gpu': node_gpu
            }
        return cluster_resources

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
                'cpu': node_cpu,
                'memory': node_memory,
                'gpu': node_gpu
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
                            'cpu'] -= parse_resource_cpu(
                                container.resources.requests.get('cpu', '0m'))
                        available_resources[node_name][
                            'memory'] -= parse_resource_memory(
                                container.resources.requests.get(
                                    'memory', '0Mi'))
                        available_resources[node_name]['gpu'] -= int(
                            container.resources.requests.get(
                                'nvidia.com/gpu', 0))
        return available_resources

    def submit_job(self, job: Job) -> None:
        """
        Submit a YAML which contains the Kubernetes Job declaration using the
        batch api.

        Args:
            job: Job object containing the YAML file.
        """
        # Parse the YAML file into a dictionary
        job_dict = self.convert_yaml(job)
        api_response = self.batch_v1.create_namespaced_job(
            namespace=self.namespace, body=job_dict)
        return api_response

    def delete_job(self, job: Job) -> None:
        job_name = job.meta.name
        self.batch_v1.delete_namespaced_job(
            name=job_name,
            namespace=self.namespace,
            body=client.V1DeleteOptions(
                propagation_policy="Foreground",
                grace_period_seconds=5  # Adjust as needed
            ))

    def convert_yaml(self, job: Job):
        """
        Serves as a compatibility layer to generate a Kubernetes-compatible
        YAML file from a job object.

        Args:
            job: Generic Job object.
        """
        dir_path = os.path.dirname(os.path.realpath(__file__))
        jinja_env = Environment(loader=FileSystemLoader(
            os.path.abspath(dir_path)),
                                autoescape=select_autoescape())
        jinja_template = jinja_env.get_template('k8_job.j2')
        jinja_dict = {
            'name': job.meta.name,
            'cluster_name': self.cluster_name,
            'image': job.spec.image,
            'run': job.spec.run,
            'cpu': job.spec.resources.get('cpu', 0),
            'gpu': job.spec.resources.get('gpu', 0),
            'replicas': job.status.clusters[self.cluster_name],
        }
        kubernetes_job = jinja_template.render(jinja_dict)
        kubernetes_job = yaml.safe_load(kubernetes_job)
        return kubernetes_job

    def get_jobs_status(self):
        """ Gets the jobs state. (Map from job name to status) """
        # Filter jobs that that are submitted by Sky Manager.
        jobs = self.batch_v1.list_namespaced_job(
            namespace=self.namespace,
            label_selector='manager=sky_manager').items

        jobs_dict = {}
        for job in jobs:
            job_name = job.metadata.name
            job_status = self._process_job_status(job)
            jobs_dict[job_name] = job_status
        return jobs_dict

    def _process_job_status(self,
                            job: models.v1_job.V1Job) -> Dict[str, JobStatus]:
        active_pods = job.status.active or 0
        succeeded_pods = job.status.succeeded or 0
        failed_pods = job.status.failed or 0
        # Update job status
        if active_pods == 0 and succeeded_pods == 0:
            # When no pods have been scheduled.
            job_status = JobStatusEnum.PENDING.value
        elif succeeded_pods == job.spec.completions:
            job_status = JobStatusEnum.COMPLETED.value
        elif failed_pods >= job.spec.backoff_limit:
            job_status = JobStatusEnum.FAILED.value
        else:
            job_status = JobStatusEnum.RUNNING.value
        return JobStatus(
            status=job_status,
            clusters = {},
        )


if __name__ == '__main__':
    cur_job_state = KubernetesManager('mluo-onprem')
    lol = yaml.safe_load(
        open(
            '/home/gcpuser/sky-manager/sky_manager/examples/example_job.yaml'))
