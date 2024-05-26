import enum
import json
import logging

import ray


class ResourceEnum(enum.Enum):
    """
    Different types of resources.
    """
    # CPUs
    CPU: str = "cpus"
    # Generic GPUs
    GPU: str = "gpus"
    # Memory is expressed in MB.
    MEMORY: str = "memory"
    # Disk is also expressed in MB.
    DISK: str = 'disk'


def fetch_allocatable_resources():
    ray.init(address='auto',
             logging_level=logging.ERROR)  # Connect to the Ray cluster

    resources = ray.cluster_resources()
    allocatable_resources = {}
    nodes = {
        name.split(':', 1)[1]: {}
        for name in resources.keys()
        if name.startswith('node:') and '__internal_head__' not in name
    }

    for node in nodes:
        if node not in allocatable_resources:
            allocatable_resources[node] = {}
        for resource_name, quantity in resources.items():
            if "object_store" in resource_name:
                allocatable_resources[node][ResourceEnum.DISK.value] = quantity
            elif "CPU" in resource_name.upper():
                allocatable_resources[node][ResourceEnum.CPU.value] = quantity
            elif "memory" in resource_name.lower():
                allocatable_resources[node][
                    ResourceEnum.MEMORY.value] = quantity / (1024**2)  # MB
            elif "GPU" in resource_name.upper():
                allocatable_resources[node][ResourceEnum.GPU.value] = quantity

    return allocatable_resources


if __name__ == "__main__":
    resources = fetch_allocatable_resources()
    print(json.dumps(resources, indent=4))
