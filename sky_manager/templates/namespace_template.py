from enum import Enum
import time
from typing import Dict, List

from pydantic import Field, field_validator

from sky_manager.templates.object_template import Object, ObjectException, \
    ObjectList, ObjectMeta, ObjectSpec, ObjectStatus


class NamespaceEnum(Enum):
    # Namespace is active.
    ACTIVE = "ACTIVE"


class NamespaceException(ObjectException):
    """Raised when the namespace dict is invalid."""
    pass


class NamespaceStatus(ObjectStatus):
    conditions: List[Dict[str, str]] = Field(default=[], validate_default=True)
    status: str = Field(default=NamespaceEnum.ACTIVE.value, validate_default=True)

    @field_validator('conditions')
    @classmethod
    def verify_conditions(cls, v: List[Dict[str, str]]):
        conditions = v
        if not conditions:
            conditions = [{
                'status': NamespaceEnum.ACTIVE.value,
                'transitionTime': str(time.time()),
            }]
        if len(conditions) == 0:
            raise NamespaceException(
                'Namespace status\'s condition field is empty.')
        for condition in conditions:
            if 'status' not in condition:
                raise NamespaceException(
                    'Namespace status\'s condition field is missing status.')
        return conditions

    @field_validator('status')
    @classmethod
    def verify_status(cls, status: str):
        if status is None or status not in NamespaceEnum.__members__:
            raise NamespaceException(f'Invalid namespace status: {status}.')
        return status

    def update_conditions(self, conditions):
        self.conditions = conditions

    def update_status(self, status: str):
        self.status = status
        # Check most recent status of the cluster.
        previous_status = self.conditions[-1]
        if previous_status['status'] != status:
            cur_time = time.time()
            self.conditions.append({
                'status': status,
                'transitionTime': str(cur_time),
            })


class NamespaceMeta(ObjectMeta):
    pass

class NamespaceSpec(ObjectSpec):
    pass


class Namespace(Object):
    metadata: NamespaceMeta = Field(default=NamespaceMeta())
    spec: NamespaceSpec = Field(default=NamespaceSpec())
    status: NamespaceStatus = Field(default=NamespaceStatus())


class NamespaceList(ObjectList):
    objects: List[Namespace] = Field(default=[])


if __name__ == '__main__':
    print(Namespace())