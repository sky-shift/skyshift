import enum


class ContainerEnum(enum.Enum):
    """Selector for supported container managers"""
    CONTAINERD = "CONTAINERD"
    SINGULARITY = "SINGULARITY"
    PODMAN = "PODMAN"
    PODMANHPC = "PODMANHPC"
    DOCKER= "DOCKER"

    def __eq__(self, other):
        if isinstance(other, str):
            return self.value == other
        return super().__eq__(other)