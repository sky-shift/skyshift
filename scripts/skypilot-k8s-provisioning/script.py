import os

import sky
import yaml


def provision_resources(num_nodes, cluster_name, run_command, resources):
    task = sky.Task(num_nodes=num_nodes,
                    setup='echo "setup"',
                    run=run_command)
    ports = ["22", "6443", "2376", "2379", "2380", "8472", "9099",
             "10250", "443", "379", "6443", "8472", "80", "472", "10254", "3389", "30000-32767"]
    if "ports" not in resources:
        resources["ports"] = ports
    else:
        resources["ports"] = list(set(resources["ports"] + ports))
    task.set_resources(sky.Resources(**resources))
    sky.launch(task, cluster_name,)


def construct_cluster_yaml(ips):
    data = {"nodes": []}
    for i in range(len(ips)):
        ip = ips[i]

        node = {
            "address": ip,
            "user": "gcpuser",  # TODO: auto detect
            "ssh_key_path": "~/.ssh/sky-key",
            "ssh_port": 22,
            "role": ["worker"]
        }

        if i == 0:
            node["role"] += ["etcd", "controlplane"]

        data["nodes"].append(node)

    with open('cluster.yml', 'w') as file:
        yaml.dump(data, file)

    os.system("rke up --config cluster.yml")


def script(cluster_name, num_nodes, run, resources={}):
    provision_resources(num_nodes, cluster_name, run, resources)
    ips = sky.status(cluster_name, True)[0]['handle'].external_ips()
    construct_cluster_yaml(ips)


script("test", 2, 'echo "Stopping Ray"')
