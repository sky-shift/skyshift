"""
SkyPilot + RKE provisioning script for cloud clusters.
"""
from copy import deepcopy
import os
import threading
from typing import Any, Dict

import sky
import yaml

from skyflow.cloud.utils import cloud_cluster_dir, skypilot_ssh_path
from skyflow.globals import USER_SSH_PATH
from skyflow.templates.cluster_template import Cluster, ClusterSpec

BASE_RKE_CLUSTER_YAML: Dict[str, Any] = {
    "nodes": [],
    "ssh_key_path": f"{USER_SSH_PATH}/sky-key",
    "ingress": {
        "provider": "nginx"
    },
    "system_images": {
        "ingress": "rancher/nginx-ingress-controller:0.21.0-rancher1",
        "ingress_backend":
        "rancher/nginx-ingress-controller-defaultbackend:1.4"
    },
}

# See here for details: https://rke.docs.rancher.com/os#ports
RKE_PORTS = [
    "22",
    "6443",
    "2376",
    "2379",
    "2380",
    "8472",
    "9099",
    "10250",
    "443",
    "379",
    "6443",
    "8472",
    "80",
    "472",
    "10254",
    "3389",
    "30000-32767",
    "7946",
    "179",
    "6783-6784",
    "9796",
    "9443",
    "9100",
    "8443",
    "4789",
]


def _construct_skypilot_task_yaml(cluster_name: str,
                                  num: int,
                                  spec: ClusterSpec,
                                  setup: str = "echo 'setup'",
                                  run: str = "echo 'run'"):
    """
    Construct a SkyPilot task YAML for the provided ClusterSpec.
    """
    spec = deepcopy(spec)
    spec.ports = list(set(spec.ports + RKE_PORTS))
    try:
        del spec.manager
        del spec.num_nodes
        del spec.attached
        del spec.config_path
    except AttributeError:
        pass
    data = {
        "name": f"sky-{cluster_name}-{num}",
        "resources": dict(spec),
        "setup": setup,
        "run": run,
    }
    # Create directioy if it does not exist
    provision_dir = f"{cloud_cluster_dir(cluster_name)}/provision"
    os.makedirs(provision_dir, exist_ok=True)

    with open(f"{provision_dir}/skypilot_task_{cluster_name}_{num}.yml",
            "w") as file:
        yaml.dump(data, file)


def _provision_resources(cluster_name: str, num_nodes: int, run_command: str,
                         spec: ClusterSpec):
    """
    Provision resources for the cluster using SkyPilot Python API.
    """
    run_command = run_command or ""
    spec = spec or ClusterSpec()

    def _create_resource(num):
        _construct_skypilot_task_yaml(cluster_name,
                                      num,
                                      spec,
                                      setup="",
                                      run=run_command)
        task = sky.Task.from_yaml(
            f"{cloud_cluster_dir(cluster_name)}/provision/skypilot_task_{cluster_name}_{num}.yml"
        )
        sky.launch(task, f"sky-{cluster_name}-{num}")

    threads: list[threading.Thread] = []
    for i in range(num_nodes):
        thread = threading.Thread(target=_create_resource, args=(i, ))
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()


def _parse_ssh_config(node_name: str):
    """
    Parse the SSH config file and return a dictionary mapping hosts to their users.
    """
    with open(skypilot_ssh_path(node_name), 'r') as file:
        lines = file.readlines()

    hostname = None
    user = None

    for line in lines:
        line = line.strip()
        if line.startswith('HostName '):
            hostname = line.split()[1]
        elif line.startswith('User '):
            user = line.split()[1]

    return (hostname, user)


def _construct_rke_cluster_yaml(cluster_name: str, num_nodes: int):
    """
    Construct the {cloud_cluster_dir(cluster_name)}/rke_cluster.yml file for RKE.
    """
    data = BASE_RKE_CLUSTER_YAML
    data["cluster_name"] = cluster_name

    for i in range(num_nodes):
        hostname, user = _parse_ssh_config(f"sky-{cluster_name}-{i}")
        node = {
            "address": hostname,
            "user": user,
            "ssh_port": 22,
            "role": ["worker"]
        }

        if i == 0:
            node["role"] += ["etcd", "controlplane"]

        data["nodes"].append(node)

    with open(f"{cloud_cluster_dir(cluster_name)}/rke_cluster.yml",
              'w') as file:
        yaml.dump(data, file)


def _cleanup_config_dir(cluster_name: str, num_nodes: int):
    """
    Cleans up the config directory after provisioning a cluster.
    """
    for i in range(num_nodes):
        try:
            os.remove(
                f"{cloud_cluster_dir(cluster_name)}/provision/skypilot_task_{cluster_name}_{i}.yml"
            )
        except FileNotFoundError:
            pass


def provision_new_kubernetes_cluster(
    cluster_obj: Cluster,
    run: str = "",
):
    """
    Provisions a new Kubernetes cluster using Skypilot and RKE.
    """
    cluster_name = cluster_obj.metadata.name
    num_nodes = cluster_obj.spec.num_nodes
    spec = cluster_obj.spec

    os.makedirs(cloud_cluster_dir(cluster_name))
    # Provision Skypilot cloud resources.
    _provision_resources(cluster_name, num_nodes, run, spec)
    # Create RKE YAML to run on the Skypilot-provisioned cluster.
    _construct_rke_cluster_yaml(cluster_name, num_nodes)
    # Launch RKE on Skypilot cluster.
    # Assumes RKE is already installed: https://rke.docs.rancher.com/installation#download-the-rke-binary
    os.system(
        f"rke up --config {cloud_cluster_dir(cluster_name)}/rke_cluster.yml")


def delete_kubernetes_cluster(cluster_name: str, num_nodes: int):
    """
    Deletes a Kubernetes cluster.
    """
    def _delete_resource(num):
        sky.down(f"sky-{cluster_name}-{num}")

    threads: list[threading.Thread] = []
    for i in range(num_nodes):
        thread = threading.Thread(target=_delete_resource, args=(i, ))
        thread.start()
        threads.append(thread)
    # Clean up Skypilot config files.
    _cleanup_config_dir(cluster_name, num_nodes)

    for thread in threads:
        thread.join()
