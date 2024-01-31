"""
Link Template for Skyflow.
"""
import enum

from pydantic import Field

from skyflow.templates.object_template import (Object, ObjectException,
                                               ObjectList, ObjectMeta,
                                               ObjectSpec, ObjectStatus)


class LinkException(ObjectException):
    """Raised when the link template is invalid."""


class LinkStatusEnum(enum.Enum):
    """Represents the network link between two clusters."""

    # When job is first created.
    INIT = "INIT"
    # When job is currently running.
    ACTIVE = "ACTIVE"
    # When a job has failed.
    FAILED = "FAILED"

    def __eq__(self, other):
        if isinstance(other, str):
            return self.value == other
        return super().__eq__(other)


class LinkStatus(ObjectStatus):
    """Status of a Link."""
    phase: str = Field(default=LinkStatusEnum.INIT.value)

    def get_status(self):
        """Returns the status of the Link."""
        return self.phase

    def update_status(self, status: str):
        """Updates the status of the Link."""
        if status not in [status.value for status in LinkStatusEnum]:
            raise LinkException(f"Invalid status: {status}")
        self.phase = status


class LinkMeta(ObjectMeta):
    """Metadata of a Link."""

class LinkSpec(ObjectSpec):
    """Spec of a Link."""
    source_cluster: str = Field(default=None)
    target_cluster: str = Field(default=None)


class Link(Object):
    """Link object."""
    kind: str = Field(default="Link", validate_default=True)
    metadata: LinkMeta = Field(default=LinkMeta(), validate_default=True)
    spec: LinkSpec = Field(default=LinkSpec(), validate_default=True)
    status: LinkStatus = Field(default=LinkStatus(), validate_default=True)

    def get_status(self):
        """Returns the status of the Link."""
        return self.status.phase # pylint: disable=no-member

    def get_namespace(self):
        """Returns the namespace of the Link."""
        return self.metadata.namespace # pylint: disable=no-member


class LinkList(ObjectList):
    """List of Links."""
    kind: str = Field(default="LinkList")
