"""
Namespace template.
"""
import enum

from pydantic import Field, field_validator

from skyshift.templates.object_template import (Object, ObjectException,
                                                ObjectList, ObjectMeta,
                                                ObjectSpec, ObjectStatus)


class NamespaceEnum(enum.Enum):
    """Enum for Namespace status."""
    # Namespace is active.
    ACTIVE = "ACTIVE"
    DELETING = "DELETING"

    def __eq__(self, other):
        if isinstance(other, str):
            return self.value == other
        return super().__eq__(other)


class NamespaceException(ObjectException):
    """Raised when the namespace dict is invalid."""


class NamespaceStatus(ObjectStatus):
    """Status of a Namespace."""
    status: str = Field(default=NamespaceEnum.ACTIVE.value,
                        validate_default=True)

    @field_validator("status")
    @classmethod
    def verify_status(cls, status: str):
        """Validates the status field of a Namespace."""
        if status is None or status not in NamespaceEnum.__members__:
            raise ValueError(f"Invalid namespace status: {status}.")
        return status

    def update_status(self, status: str):
        """Updates the status field of a Namespace."""
        # Check if status in enum.
        if status is None or status not in NamespaceEnum.__members__:
            raise ValueError(f"Invalid namespace status: {status}.")
        self.status = status


class NamespaceMeta(ObjectMeta):
    """Metadata of a Namespace."""


class NamespaceSpec(ObjectSpec):
    """Spec of a Namespace."""


class Namespace(Object):
    """Namespace object."""
    metadata: NamespaceMeta = Field(default=NamespaceMeta())
    spec: NamespaceSpec = Field(default=NamespaceSpec())
    status: NamespaceStatus = Field(default=NamespaceStatus())


class NamespaceList(ObjectList):
    """List of Namespaces."""


if __name__ == "__main__":
    print(Namespace())
