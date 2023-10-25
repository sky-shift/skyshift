import os
import threading

import sky
import yaml


def provision_resources(num_nodes, cluster_name, run_command, resources):
    """
    Provision resources for the cluster using SkyPilot Python API.
    """
    def create_resource(num):
        task = sky.Task(setup='echo "setup"',
                        run=run_command)
        ports = ["22", "6443", "2376", "2379", "2380", "8472", "9099",
                 "10250", "443", "379", "6443", "8472", "80", "472", "10254", "3389", "30000-32767"]
        if "ports" not in resources:
            resources["ports"] = ports
        else:
            resources["ports"] = list(set(resources["ports"] + ports))
        task.set_resources(sky.Resources(**resources))
        sky.launch(task, f"skym-{cluster_name}-{num}",)

    threads = []
    for i in range(num_nodes):
        thread = threading.Thread(target=create_resource, args=(i,))
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()


def parse_ssh_config():
    """
    Parse the SSH config file and return a dictionary mapping hosts to their users.
    """
    with open(os.path.expanduser("~/.ssh/config"), 'r') as f:
        lines = f.readlines()

    current_host = None
    host_details = {}
    prev_line = None

    for line in lines:
        line = line.strip()

        if prev_line and prev_line.startswith("# Added by sky") and line.startswith('Host '):
            current_host = line.split()[1]
            host_details[current_host] = {}
        elif current_host:
            if line.startswith('HostName '):
                host_details[current_host]['hostname'] = line.split()[1]
            elif line.startswith('User '):
                host_details[current_host]['user'] = line.split()[1]

        prev_line = line

    return host_details


def construct_cluster_yaml(cluster_name, num_nodes):
    """
    Construct the cluster.yml file for RKE.
    """
    data = {"nodes": []}
    host_details = parse_ssh_config()
    print(host_details)
    for i in range(num_nodes):
        details = host_details[f"skym-{cluster_name}-{i}"]
        node = {
            "address": details["hostname"],
            "user": details["user"],
            "ssh_key_path": os.path.expanduser("~/.ssh/sky-key"),
            "ssh_port": 22,
            "role": ["worker"]
        }

        if i == 0:
            node["role"] += ["etcd", "controlplane"]

        data["nodes"].append(node)

    with open('cluster.yml', 'w') as file:
        yaml.dump(data, file)


def script(cluster_name, num_nodes, run, resources={}):
    provision_resources(num_nodes, cluster_name, run, resources)
    construct_cluster_yaml(cluster_name, num_nodes)
    os.system("rke up --config cluster.yml")


script("test", 2, 'echo "Stopping Ray"')
