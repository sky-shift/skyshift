"""
Link Template for Skyshift.
"""
import enum
from typing import Optional

from pydantic import Field, field_validator

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

    def __eq__(self, other_link):
        if isinstance(other_link, str):
            return self.value == other_link
        return super().__eq__(other_link)


class LinkStatus(ObjectStatus):
    """Status of a Link."""
    phase: str = Field(default=LinkStatusEnum.INIT.value)

    @field_validator('phase')
    @classmethod
    def validate_phase(cls, phase: str) -> str:
        """
        Validates the phase field. Ensures it is a valid status according to LinkStatusEnum.
        """
        if phase not in [status.value for status in LinkStatusEnum]:
            raise ValueError(f"Invalid status: {phase}")
        return phase

    def get_status(self) -> str:
        """Returns the status of the Link."""
        return self.phase

    def update_status(self, status: str) -> None:
        """Updates the status of the Link."""
        if status not in [status.value for status in LinkStatusEnum]:
            raise ValueError(f"Invalid status: {status}")
        self.phase = status


class LinkMeta(ObjectMeta):
    """Metadata of a Link."""


class LinkSpec(ObjectSpec):
    """Spec of a Link."""
    source_cluster: Optional[str] = Field(default=None)
    target_cluster: Optional[str] = Field(default=None)

    @field_validator('source_cluster')
    @classmethod
    def validate_source_cluster(
            cls, source_cluster: Optional[str]) -> Optional[str]:
        """
        Validates the source cluster field. If provided, it must be a non-empty string.
        """
        if source_cluster is not None and (not isinstance(source_cluster, str)
                                           or source_cluster.strip() == ""):
            raise ValueError(
                "Source cluster must be a non-empty string or None.")
        return source_cluster

    @field_validator('target_cluster')
    @classmethod
    def validate_target_cluster(
            cls, target_cluster: Optional[str]) -> Optional[str]:
        """
        Validates the target cluster field. If provided, it must be a non-empty string.
        """
        if target_cluster is not None and (not isinstance(target_cluster, str)
                                           or target_cluster.strip() == ""):
            raise ValueError(
                "Target cluster must be a non-empty string or None.")
        return target_cluster


class Link(Object):
    """Link object."""
    kind: str = Field(default="Link", validate_default=True)
    metadata: LinkMeta = Field(default=LinkMeta(), validate_default=True)
    spec: LinkSpec = Field(default=LinkSpec(), validate_default=True)
    status: LinkStatus = Field(default=LinkStatus(), validate_default=True)

    def get_status(self):
        """Returns the status of the Link."""
        return self.status.phase  # pylint: disable=no-member

    def get_namespace(self):
        """Returns the namespace of the Link."""
        return self.metadata.namespace  # pylint: disable=no-member


class LinkList(ObjectList):
    """List of Links."""
    kind: str = Field(default="LinkList")
