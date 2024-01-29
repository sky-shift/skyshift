from enum import Enum


class ResourceEnum(Enum):
    # CPUs
    CPU: str = 'cpus'
    # Generic GPUs
    GPU: str = 'gpus'
    # Memory is expressed in MB.
    MEMORY: str = 'memory'
    # Disk is also expressed in MB.
    DISK: str = 'DISK'


# TODO: Expand list of accelerators
class AcceleratorEnum(Enum):
    T4: str = 'T4'
    L4: str = 'L4'
    P4: str = 'P4'
    V100: str = 'V100'
    A100: str = 'A100'
    P100: str = 'P100'
    K80: str = 'K80'
    H100: str = 'H100'
