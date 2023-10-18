from enum import Enum


class ResourceEnum(Enum):
    CPU = 'cpu'
    GPU = 'gpu'
    # Memory is expressed in MB.
    MEMORY = 'memory'
    # Disk is also expressed in MB.
    DISK = 'disk'