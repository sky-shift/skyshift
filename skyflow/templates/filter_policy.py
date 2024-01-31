"""
FilterPolicy - A FilterPolicy is a set of rules that governs the filters
for clusters that a job can be scheduled on.
"""
import enum
import time
from typing import Dict, List

from pydantic import BaseModel, Field, field_validator

from skyflow.templates.object_template import (Object, ObjectException,
                                               ObjectList, ObjectMeta,
                                               ObjectSpec, ObjectStatus)

DEFAULT_NAMESPACE = "default"


class FilterPolicyException(ObjectException):
    """Raised when the filter policy is invalid."""


class FilterStatusEnum(enum.Enum):
    """Enum for Filter Policy status."""
    # Status when Filter policy is active.
    ACTIVE = "ACTIVE"


class FilterPolicyStatus(ObjectStatus):
    """Status of a Filter Policy."""
    conditions: List[Dict[str, str]] = Field(default=[], validate_default=True)
    status: str = Field(default=FilterStatusEnum.ACTIVE.value,
                        validate_default=True)

    @field_validator("conditions")
    @classmethod
    def verify_conditions(cls, value: List[Dict[str, str]]):
        """Validates the conditions field of a Filter Policy."""
        conditions = value
        if not conditions:
            conditions = [{
                "status": FilterStatusEnum.ACTIVE.value,
                "transitionTime": str(time.time()),
            }]
        if len(conditions) == 0:
            raise ValueError(
                "Filter Policy status's condition field is empty.")
        for condition in conditions:
            if "status" not in condition:
                raise ValueError(
                    "Filter Policy's condition field is missing status.")
        return conditions

    @field_validator("status")
    @classmethod
    def verify_status(cls, status: str):
        """Validates the status field of a Filter Policy."""
        if status is None or status not in FilterStatusEnum.__members__:
            raise ValueError(f"Invalid Filter Policy status: {status}.")
        return status

    def update_conditions(self, conditions):
        """Updates the conditions field of a Filter Policy."""
        self.conditions = conditions

    def update_status(self, status: str):
        """Updates the status field of a Filter Policy."""
        self.status = status
        # Check most recent status of the cluster.
        previous_status = self.conditions[-1]
        if previous_status["status"] != status:
            cur_time = time.time()
            self.conditions.append({
                "status": status,
                "transitionTime": str(cur_time),
            })


class FilterPolicyMeta(ObjectMeta):
    """Metadata for a Filter Policy."""
    namespace: str = Field(default=DEFAULT_NAMESPACE, validate_default=True)

    @field_validator("namespace")
    @classmethod
    def verify_namespace(cls, value: str) -> str:
        """Validates the namespace field of a Filter Policy."""
        if not value:
            raise ValueError("Namespace cannot be empty.")
        return value


class ClusterFilter(BaseModel):
    """ClusterFilter object in the FilterPolicy spec."""
    include: List[str] = Field(default=[])
    exclude: List[str] = Field(default=[])


class FilterPolicySpec(ObjectSpec):
    """Spec for a Filter Policy."""
    cluster_filter: ClusterFilter = Field(default=ClusterFilter(),
                                          validate_default=True)
    labels_selector: Dict[str, str] = Field(default={}, validate_default=True)


class FilterPolicy(Object):
    """Filter Policy object."""
    metadata: FilterPolicyMeta = Field(default=FilterPolicyMeta(),
                                       validate_default=True)
    spec: FilterPolicySpec = Field(default=FilterPolicySpec(),
                                   validate_default=True)
    status: FilterPolicyStatus = Field(default=FilterPolicyStatus(),
                                       validate_default=True)

    def get_namespace(self):
        """Returns the namespace of the Filter Policy."""
        return self.metadata.namespace # pylint: disable=no-member


class FilterPolicyList(ObjectList):
    """List of Filter Policies."""
    kind: str = Field(default="FilterPolicyList")


if __name__ == "__main__":
    print(FilterPolicy())
    print(FilterPolicyList())
