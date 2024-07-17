"""
SkyPilot + RKE provisioning script for cloud clusters.
"""
import os
import threading

import sky
import yaml

from skyshift.cloud.utils import (RKE_PORTS, cloud_cluster_dir,
                                  create_ssh_scp_clients, parse_ssh_config)
from skyshift.templates.cluster_template import Cluster, ClusterSpec
from skyshift.utils.scp_utils import get_scp_async, send_scp_sync
from skyshift.utils.ssh_utils import ssh_send_command

RKE2_SETUP_SCRIPT: str = "./skyshift/cloud/rke2_setup.sh"
RKE2_ADD_AGENT_SCRIPT: str = "./skyshift/cloud/rke2_add_agent.sh"


def _cleanup_config_dir(cluster_name: str, num_nodes: int):
    """
    Cleans up the config directory after provisioning a cluster.
    """
    for i in range(num_nodes):
        try:
            os.remove(
                f"{cloud_cluster_dir(cluster_name)}/provision/skypilot_provision_task_{cluster_name}_{i}.yml"
            )
        except FileNotFoundError:
            pass


def _construct_skypilot_task_yaml(cluster_name: str,
                                  num: int,
                                  spec: ClusterSpec,
                                  envs: dict = {}):
    """
    Construct a SkyPilot task YAML for the provided ClusterSpec.
    """
    data = {
        "name": f"sky-{cluster_name}-{num}",
        "resources": {
            "cpus": spec.cpus,
            "memory": spec.memory,
            "disk_size": spec.disk_size,
            "accelerators": spec.accelerators,
            "ports": list(set(spec.ports + RKE_PORTS)),
            "cloud": spec.cloud,
            "region": spec.region,
        },
        "envs": envs,
    }
    # Create directioy if it does not exist
    provision_dir = f"{cloud_cluster_dir(cluster_name)}/provision"
    os.makedirs(provision_dir, exist_ok=True)

    with open(
            f"{provision_dir}/skypilot_provision_task_{cluster_name}_{num}.yml",
            "w") as file:
        yaml.dump(data, file)


def create_resource(cluster_name, num, spec, envs=None):
    """
    Creates a new node using Skypilot.
    """
    skypilot_cluster_name = f"sky-{cluster_name}-{num}"
    _construct_skypilot_task_yaml(cluster_name, num, spec, envs)
    task = sky.Task.from_yaml(
        f"{cloud_cluster_dir(cluster_name)}/provision/skypilot_provision_task_{cluster_name}_{num}.yml"
    )
    sky.launch(task, skypilot_cluster_name)
    return skypilot_cluster_name


def provision_new_kubernetes_cluster(cluster_obj: Cluster):
    """
    Provisions a new Kubernetes cluster using Skypilot and RKE.
    """
    cluster_name = cluster_obj.metadata.name
    spec = cluster_obj.spec

    # Provision the SkyPilot node
    os.makedirs(cloud_cluster_dir(cluster_name))
    skypilot_node = create_resource(cluster_name, 0, spec)
    cluster_ip = parse_ssh_config(skypilot_node)

    # Copy over RKE2 setup script and run it
    (ssh_client, scp_client) = create_ssh_scp_clients(skypilot_node)
    send_scp_sync(scp_client, {RKE2_SETUP_SCRIPT: "/tmp/rke2_setup.sh"})
    ssh_send_command(ssh_client, "sudo chmod +x /tmp/rke2_setup.sh")
    envs = {"PUBLIC_IP": cluster_ip, "CLUSTER_NAME": cluster_name}
    env_command = ' '.join(f"{key}='{value}'" for key, value in envs.items())
    ssh_send_command(ssh_client,
                     f"sudo -E bash -c '{env_command} /tmp/rke2_setup.sh'")

    # Copy over RKE2 cluster token (/var/lib/rancher/rke2/server/node-token)
    # and kubeconfig (/etc/rancher/rke2/rke2.yaml)
    get_scp_async(
        ssh_client, {
            f"{cloud_cluster_dir(cluster_name)}/kubeconfig":
            "/etc/rancher/rke2/rke2.yaml",
            f"{cloud_cluster_dir(cluster_name)}/RKE2_TOKEN":
            "/var/lib/rancher/rke2/server/node-token"
        })

    rke2_token = open(
        f"{cloud_cluster_dir(cluster_name)}/RKE2_TOKEN").read().strip()

    return cluster_ip, rke2_token


def add_node_to_cluster(cluster_obj: Cluster, num: int, cluster_ip: str,
                        rke2_token: str):
    """
    Adds a new node to a Kubernetes cluster.
    """
    cluster_name = cluster_obj.metadata.name
    spec = cluster_obj.spec
    skypilot_node = create_resource(cluster_name, num, spec)

    # Copy over RKE2 add agent script and run it
    (ssh_client, scp_client) = create_ssh_scp_clients(skypilot_node)
    send_scp_sync(scp_client,
                  {RKE2_ADD_AGENT_SCRIPT: "/tmp/rke2_add_agent.sh"})
    ssh_send_command(ssh_client, "sudo chmod +x /tmp/rke2_add_agent.sh")
    envs = {"PUBLIC_IP": cluster_ip, "RKE2_TOKEN": rke2_token}
    env_command = ' '.join(f"{key}='{value}'" for key, value in envs.items())
    ssh_send_command(
        ssh_client, f"sudo -E bash -c '{env_command} /tmp/rke2_add_agent.sh'")


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
