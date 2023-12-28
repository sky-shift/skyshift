from copy import deepcopy
import datetime
import enum
from typing import Any, Dict, List

from pydantic import Field, field_validator

from sky_manager.templates.object_template import Object, ObjectException, \
    ObjectList, ObjectMeta, ObjectSpec, ObjectStatus


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

    def update_status(self, status: str):
        if status is None or status not in LinkStatusEnum.__members__:
            raise ObjectException(f'Invalid link status: {status}.')
        # Check most recent status of the cluster.
        previous_status = self.conditions[-1]
        if previous_status['type'] != status:
            time_str = datetime.datetime.utcnow().isoformat()
            self.conditions.append({
                'type': status,
                'transition_time': time_str,
                'update_time': time_str,
            })
        else:
            previous_status['update_time'] = datetime.datetime.utcnow().isoformat()


class LinkMeta(ObjectMeta):
    pass

class LinkSpec(ObjectSpec):
    pass


class Link(Object):
    metadata: LinkMeta = Field(default=LinkMeta(), validate_default=True)
    spec: LinkSpec = Field(default=LinkSpec(), validate_default=True)
    status: LinkStatus = Field(default=LinkStatus(), validate_default=True)
    
    def get_namespace(self):
        return self.metadata.namespace


class LinkList(ObjectList):
    objects: List[Link] = Field(default=[])

