"""
FilterPolicy - A FilterPolicy is a set of rules that governs the filters
for clusters that a job can be scheduled on.
"""
import enum
from typing import Dict, List

from pydantic import BaseModel, Field, field_validator

from skyshift.templates.object_template import (NamespacedObjectMeta, Object,
                                               ObjectException, ObjectList,
                                               ObjectSpec, ObjectStatus)


class FilterPolicyException(ObjectException):
    """Raised when the filter policy is invalid."""


class FilterStatusEnum(enum.Enum):
    """Enum for Filter Policy status."""
    # Status when Filter policy is active.
    ACTIVE = "ACTIVE"

    def __eq__(self, other):
        if isinstance(other, str):
            return self.value == other
        return super().__eq__(other)


class FilterPolicyStatus(ObjectStatus):
    """Status of a Filter Policy."""
    status: str = Field(default=FilterStatusEnum.ACTIVE.value,
                        validate_default=True)

    @field_validator("status")
    @classmethod
    def verify_status(cls, status: str):
        """Validates the status field of a Filter Policy."""
        if status is None or status not in FilterStatusEnum.__members__:
            raise ValueError(f"Invalid Filter Policy status: {status}.")
        return status


class FilterPolicyMeta(NamespacedObjectMeta):
    """Metadata for a Filter Policy."""


class ClusterFilter(BaseModel):
    """ClusterFilter object in the FilterPolicy spec."""
    include: List[str] = Field(default=[])
    exclude: List[str] = Field(default=[])

    @field_validator('include', 'exclude')
    @classmethod
    def check_non_empty_strings(cls, value: List[str]) -> List[str]:
        """
        Ensures that the include and exclude lists contain only non-empty strings.
        """
        if any(not item.strip() for item in value):
            raise ValueError("List must not contain empty strings.")
        return value


class FilterPolicySpec(ObjectSpec):
    """Spec for a Filter Policy."""
    cluster_filter: ClusterFilter = Field(default=ClusterFilter(),
                                          validate_default=True)
    labels_selector: Dict[str, str] = Field(default={}, validate_default=True)

    @field_validator('labels_selector')
    @classmethod
    def check_non_empty_strings(cls, value: Dict[str, str]) -> Dict[str, str]:
        """
        Ensures that the labels_selector contains only non-empty strings.
        """
        if any(not key.strip() or not value.strip()
               for key, value in value.items()):
            raise ValueError("Labels' keys and values can't be empty strings.")
        return value


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
        return self.metadata.namespace  # pylint: disable=no-member


class FilterPolicyList(ObjectList):
    """List of Filter Policies."""
    kind: str = Field(default="FilterPolicyList")


if __name__ == "__main__":
    print(FilterPolicy())
    print(FilterPolicyList())
