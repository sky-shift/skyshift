import enum
from typing import List

from pydantic import Field

from skyflow.templates.object_template import Object, ObjectException, \
    ObjectList, ObjectMeta, ObjectSpec, ObjectStatus


class LinkException(ObjectException):
    pass

class LinkStatusEnum(enum.Enum):
    """Represents the network link between two clusters."""
    # When job is first created.
    INIT = 'INIT'
    # When job is currently running.
    ACTIVE = 'ACTIVE'
    # When a job has failed.
    FAILED = 'FAILED'

    def __eq__(self, other):
        if isinstance(other, str):
            return self.value == other
        return super().__eq__(other)

class LinkStatus(ObjectStatus):
    phase: str = Field(default=LinkStatusEnum.INIT.value)

    def get_status(self):
        return self.phase

    def update_status(self, status: str):
        if status not in [status.value for status in LinkStatusEnum]:
            raise LinkException(f'Invalid status: {status}')
        self.phase = status


class LinkMeta(ObjectMeta):
    pass

class LinkSpec(ObjectSpec):
    source_cluster: str = Field(default=None)
    target_cluster: str = Field(default=None)


class Link(Object):
    kind: str = Field(default='Link', validate_default=True)
    metadata: LinkMeta = Field(default=LinkMeta(), validate_default=True)
    spec: LinkSpec = Field(default=LinkSpec(), validate_default=True)
    status: LinkStatus = Field(default=LinkStatus(), validate_default=True)
    
    def get_status(self):
        return self.status.phase

    def get_namespace(self):
        return self.metadata.namespace


class LinkList(ObjectList):
    objects: List[Link] = Field(default=[])

