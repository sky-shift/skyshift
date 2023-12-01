from enum import Enum


class ResourceEnum(Enum):
    # CPUs
    CPU = 'cpus'
    # Generic GPUs
    GPU = 'gpus'
    # Memory is expressed in MB.
    MEMORY = 'memory'
    # Disk is also expressed in MB.
    DISK = 'DISK'

# TODO: Expand list of accelerators
class AcceleratorEnum(Enum):
    T4 = 'T4'
    L4 = 'L4'
    P4 = 'P4'
    V100 = 'V100'
    A100 = 'A100'
    P100 = 'P100'
    K80 = 'K80'
    H100 = 'H100'
