import enum
import time
from typing import Any, Dict, List

from pydantic import BaseModel, Field, field_validator

from skyflow.templates.object_template import (Object, ObjectException,
                                               ObjectList, ObjectMeta,
                                               ObjectSpec, ObjectStatus)

DEFAULT_NAMESPACE = 'default'


class FilterPolicyException(ObjectException):
    "Raised when the filter policy is invalid."
    pass


class FilterStatusEnum(enum.Enum):
    # Status when Filter policy is active.
    ACTIVE = "ACTIVE"


class FilterPolicyStatus(ObjectStatus):
    conditions: List[Dict[str, str]] = Field(default=[], validate_default=True)
    status: str = Field(default=FilterStatusEnum.ACTIVE.value,
                        validate_default=True)

    @field_validator('conditions')
    @classmethod
    def verify_conditions(cls, v: List[Dict[str, str]]):
        conditions = v
        if not conditions:
            conditions = [{
                'status': FilterStatusEnum.ACTIVE.value,
                'transitionTime': str(time.time()),
            }]
        if len(conditions) == 0:
            raise ValueError(
                'Filter Policy status\'s condition field is empty.')
        for condition in conditions:
            if 'status' not in condition:
                raise ValueError(
                    'Filter Policy\'s condition field is missing status.')
        return conditions

    @field_validator('status')
    @classmethod
    def verify_status(cls, status: str):
        if status is None or status not in FilterStatusEnum.__members__:
            raise ValueError(f'Invalid Filter Policy status: {status}.')
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


class FilterPolicyMeta(ObjectMeta):
    namespace: str = Field(default=DEFAULT_NAMESPACE, validate_default=True)

    @field_validator('namespace')
    @classmethod
    def verify_namespace(cls, v: str) -> str:
        if not v:
            raise ValueError('Namespace cannot be empty.')
        return v


class ClusterFilter(BaseModel):
    include: List[str] = Field(default=[])
    exclude: List[str] = Field(default=[])


class FilterPolicySpec(ObjectSpec):
    cluster_filter: ClusterFilter = Field(default=ClusterFilter(),
                                          validate_default=True)
    labels_selector: Dict[str, str] = Field(default={}, validate_default=True)


class FilterPolicy(Object):
    metadata: FilterPolicyMeta = Field(default=FilterPolicyMeta(),
                                       validate_default=True)
    spec: FilterPolicySpec = Field(default=FilterPolicySpec(),
                                   validate_default=True)
    status: FilterPolicyStatus = Field(default=FilterPolicyStatus(),
                                       validate_default=True)

    def get_namespace(self):
        return self.metadata.namespace


class FilterPolicyList(ObjectList):
    kind: str = Field(default='FilterPolicyList')


if __name__ == '__main__':
    print(FilterPolicy())
    print(FilterPolicyList())
