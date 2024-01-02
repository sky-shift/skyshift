from copy import deepcopy
import datetime
import enum
from typing import Optional, Dict, List

from pydantic import BaseModel, Field, field_validator

from skyflow.templates.object_template import Object, ObjectException, \
    ObjectList, ObjectMeta, ObjectSpec, ObjectStatus
from skyflow.templates.resource_template import ResourceEnum

DEFAULT_IMAGE = 'ubuntu:latest'
DEFAULT_JOB_RESOURCES = {
    ResourceEnum.CPU.value: 1,
    ResourceEnum.MEMORY.value: 0,
}
DEFAULT_NAMESPACE = 'default'

class ServiceType(enum.Enum):
    ClusterIP = 'ClusterIP'
    LoadBalancer = 'LoadBalancer'
    ExternalName = 'ExternalName'

    def __eq__(self, other):
        if isinstance(other, str):
            return self.value == other
        return super().__eq__(other)


class ServiceException(ObjectException):
    """Raised when the job template is invalid."""
    pass


class ServiceStatus(ObjectStatus):
    external_ip: Optional[str] = Field(default=None)
    pass


class ServiceMeta(ObjectMeta):
    namespace: str = Field(default=DEFAULT_NAMESPACE, validate_default=True)

    @field_validator('namespace')
    @classmethod
    def verify_namespace(cls, v: str) -> str:
        if not v:
            raise ValueError('Namespace cannot be empty.')
        return v


class ServicePorts(BaseModel):
    port: int = Field(default=None, validate_default=True)
    target_port: int = Field(default=None, validate_default=True)
    protocol: str =  Field(default='TCP', validate_default=True)
    

class ServiceSpec(ObjectSpec):
    type: str = Field(default='ClusterIP', validate_default=True)
    selector: Dict[str, str] = Field(default={}, validate_default=True)
    ports: List[ServicePorts] = Field(default=[], validate_default=True)
    cluster_ip: Optional[str] = Field(default='')
    primary_cluster: Optional[str] = Field(default='')

    @field_validator('type')
    @classmethod
    def verify_service_type(cls, type: str) -> str:
        if type is None or type not in [r.value for r in ServiceType]:
            raise ServiceException(f'Invalid service type: {type}.')
        return type
    




class Service(Object):
    kind: str = Field(default='Service', validate_default=True)
    metadata: ServiceMeta = Field(default=ServiceMeta(), validate_default=True)
    spec: ServiceSpec = Field(default=ServiceSpec(), validate_default=True)
    status: ServiceStatus = Field(default=ServiceStatus(), validate_default=True)
    
    def get_namespace(self):
        return self.metadata.namespace


class ServiceList(ObjectList):
    objects: List[Service] = Field(default=[])

if __name__ == '__main__':
    print(ServiceList())
