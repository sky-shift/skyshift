"""
Cluster Template - Defines the Cluster object.
"""
import enum
import time
from typing import Dict, List

from pydantic import Field, field_validator

from skyflow import utils
from skyflow.templates.object_template import (Object, ObjectException,
                                               ObjectList, ObjectMeta,
                                               ObjectSpec, ObjectStatus)
from skyflow.templates.resource_template import AcceleratorEnum, ResourceEnum


class ClusterStatusEnum(enum.Enum):
    """Enum for Cluster status."""
    # Setting up cluster.
    INIT = "INIT"
    # Cluster is ready to accept jobs.
    READY = "READY"
    # Cluster is in error state.
    # This state is reached when the cluster fails several heartbeats or is not a valid cluster.
    ERROR = "ERROR"

    def __eq__(self, other):
        if isinstance(other, str):
            return self.value == other
        return super().__eq__(other)


class ClusterException(ObjectException):
    """Raised when the cluster template is invalid."""


class ClusterStatus(ObjectStatus):
    """Status of a Cluster."""
    status: str = Field(default=ClusterStatusEnum.INIT.value,
                        validate_default=True)
    # Allocatable capacity of the cluser.
    allocatable_capacity: Dict[str, Dict[str,
                                         float]] = Field(default={},
                                                         validate_default=True)
    # Total capacity of the cluster.
    capacity: Dict[str, Dict[str, float]] = Field(default={},
                                                  validate_default=True)
    # If inter-cluster networking has been installed and enabled on the cluster.
    network_enabled: bool = Field(default=False)

    # Dict mapping node names to accelerator types.
    accelerator_types: Dict[str, str] = Field(default={},
                                              validate_default=True)

    @field_validator("conditions")
    @classmethod
    def verify_cluster_conditions(cls, value: List[Dict[str, str]]):
        """Validates the conditions field of a Cluster."""
        conditions = value
        if not conditions:
            conditions = [{
                "status": ClusterStatusEnum.INIT.value,  # pylint: disable=no-member
                "transitionTime": str(time.time()),
            }]
        if len(conditions) == 0:
            raise ValueError("Cluster status's condition field is empty.")
        for condition in conditions:
            if "status" not in condition:
                raise ValueError(
                    "Cluster status's condition field is missing status.")
        return conditions

    @field_validator("capacity", "allocatable_capacity")
    @classmethod
    def verify_capacity(cls, capacity: Dict[str, Dict[str, float]]):
        """Validates the capacity and allocatable_capacity fields of a Cluster."""
        resource_enum_dict = [m.value for m in ResourceEnum]
        accelerator_enum_dict = [m.value for m in AcceleratorEnum]

        # Define resource limits (if applicable)
        resource_limits = {
            ResourceEnum.CPU.value: {
                "min": 0
            },  # Minimum 0 CPUs
            ResourceEnum.GPU.value: {
                "min": 0
            },  # Minimum 0 GPUs
            ResourceEnum.MEMORY.value: {
                "min": 0
            },  # Minimum 0 MB
            ResourceEnum.DISK.value: {
                "min": 0
            },  # Minimum 0 MB
        }

        for node_name, node_resources in capacity.items():
            for resource_type, resource_value in node_resources.items():
                if resource_type not in resource_enum_dict + accelerator_enum_dict:
                    raise ValueError(
                        f"Invalid resource type '{resource_type}' for node '{node_name}'. "
                        "Please use ResourceEnum or AcceleratorEnum to specify resources."
                    )
                if resource_type in resource_limits:
                    min_limit = resource_limits[resource_type].get(
                        "min", float("-inf"))
                    if resource_value < min_limit:
                        raise ValueError(
                            f"Invalid value for resource '{resource_type}' in node \
                                '{node_name}': {resource_value}. "
                            f"Value must be >= {min_limit}.")
                else:
                    # For accelerators or any other resources without defined limits
                    if resource_value < 0:
                        raise ValueError(
                            f"Invalid value for resource '{resource_type}' in node \
                                '{node_name}': {resource_value}. "
                            "Value must be non-negative.")

        return capacity

    @field_validator("status")
    @classmethod
    def verify_status(cls, status: str):
        """Validates the status field of a Cluster."""
        if status is None or status not in ClusterStatusEnum.__members__:
            raise ValueError(f"Invalid cluster status: {status}.")
        return status

    def update_conditions(self, conditions):
        """Updates the conditions field of a Cluster."""
        self.conditions = conditions

    def update_accelerator_types(self, accelerator_types):
        """Updates the accelerator_types field of a Cluster."""
        self.accelerator_types = accelerator_types

    def update_status(self, status: str):
        """Updates the status field of a Cluster."""
        self.status = status
        # Check most recent status of the cluster.
        previous_status = self.conditions[-1]
        if previous_status["status"] != status:
            cur_time = time.time()
            self.conditions.append({
                "status": status,
                "transitionTime": str(cur_time),
            })

    def update_capacity(self, capacity: Dict[str, Dict[str, float]]):
        """Updates the capacity field of a Cluster."""
        self.capacity = capacity

    def update_allocatable_capacity(self, capacity: Dict[str, Dict[str,
                                                                   float]]):
        """Updates the allocatable_capacity field of a Cluster."""
        self.allocatable_capacity = capacity


class ClusterMeta(ObjectMeta):
    """Metadata for a Cluster."""
    name: str = Field(default="cluster", validate_default=True)

    @field_validator("name")
    @classmethod
    def verify_name(cls, value: str) -> str:
        """Validates the name field of a Cluster,
        ensuring it does not contain whitespaces or '/'."""
        return utils.sanitize_cluster_name(value)


class ClusterSpec(ObjectSpec):
    """Spec for a Cluster."""
    manager: str = Field(default="k8", validate_default=True)

    @field_validator("manager")
    @classmethod
    def verify_manager(cls, manager: str) -> str:
        """Validates the manager field of a Cluster."""
        if not manager:
            raise ValueError(
                "Cluster spec requires `manager` field to be filled in.")
        return manager


class Cluster(Object):
    """Cluster object."""
    metadata: ClusterMeta = Field(default=ClusterMeta())
    spec: ClusterSpec = Field(default=ClusterSpec())
    status: ClusterStatus = Field(default=ClusterStatus())


class ClusterList(ObjectList):
    """List of Cluster objects."""
    kind: str = Field(default="ClusterList")


if __name__ == "__main__":
    print(ClusterSpec(manager="k8"))
