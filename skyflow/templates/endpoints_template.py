from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from skyflow.templates.object_template import Object, ObjectException, \
    ObjectList, ObjectMeta, ObjectSpec, ObjectStatus


class EndpointsException(ObjectException):
    """Raised when the job template is invalid."""
    pass

class EndpointsStatus(ObjectStatus):
    pass

class EndpointsMeta(ObjectMeta):
    namespace: str = Field(default='default', validate_default=True)

    @field_validator('namespace')
    @classmethod
    def verify_namespace(cls, v: str) -> str:
        if not v:
            raise ValueError('Namespace cannot be empty.')
        return v

class EndpointObject(BaseModel):
    # Num endpoints to make in endpoints yaml of the primary cluster.
    num_endpoints: int = Field(default=0, validate_default=True)
    # This is exposed ip and port on the primary cluster.
    exposed_to_cluster: bool = Field(default=False, validate_default=True)


class EndpointsSpec(ObjectSpec):
    selector: Dict[str, str] = Field(default={}, validate_default=True)
    # Maps cluster name to Endpoint object.
    endpoints: Dict[str, EndpointObject] = Field(default={}, validate_default=True)
    primary_cluster: Optional[str] = Field(default='')
    

class Endpoints(Object):
    kind: str = Field(default='Endpoints', validate_default=True)
    metadata: EndpointsMeta = Field(default=EndpointsMeta(), validate_default=True)
    spec: EndpointsSpec = Field(default=EndpointsSpec(), validate_default=True)
    status: EndpointsStatus = Field(default=EndpointsStatus(), validate_default=True)
    
    def get_namespace(self):
        return self.metadata.namespace


class EndpointsList(ObjectList):
    objects: List[Endpoints] = Field(default=[])
