"""Service template for Skyflow."""
import enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from skyflow.templates.object_template import (Object, ObjectException,
                                               ObjectList, ObjectMeta,
                                               ObjectSpec, ObjectStatus)


DEFAULT_NAMESPACE = "default"


class ServiceType(enum.Enum):
    """Enum for Service type."""
    ClusterIP = "ClusterIP" # pylint: disable=invalid-name
    LoadBalancer = "LoadBalancer" # pylint: disable=invalid-name
    ExternalName = "ExternalName" # pylint: disable=invalid-name

    def __eq__(self, other):
        if isinstance(other, str):
            return self.value == other
        return super().__eq__(other)


class ServiceException(ObjectException):
    """Raised when the job template is invalid."""


class ServiceStatus(ObjectStatus):
    """Status of a Service."""
    external_ip: Optional[str] = Field(default=None)


class ServiceMeta(ObjectMeta):
    """Metadata of a Service."""
    namespace: str = Field(default=DEFAULT_NAMESPACE, validate_default=True)

    @field_validator("namespace")
    @classmethod
    def verify_namespace(cls, value: str) -> str:
        """Validates the namespace field of a Service."""
        if not value:
            raise ValueError("Namespace cannot be empty.")
        return value


class ServicePorts(BaseModel):
    """Ports of a Service."""
    port: int = Field(default=None, validate_default=True)
    target_port: int = Field(default=None, validate_default=True)
    protocol: str = Field(default="TCP", validate_default=True)


class ServiceSpec(ObjectSpec):
    """Spec of a Service."""
    type: str = Field(default="ClusterIP", validate_default=True)
    selector: Dict[str, str] = Field(default={}, validate_default=True)
    ports: List[ServicePorts] = Field(default=[], validate_default=True)
    cluster_ip: Optional[str] = Field(default="")
    primary_cluster: Optional[str] = Field(default="")

    @field_validator("type")
    @classmethod
    def verify_service_type(cls, service_type: str) -> str:
        """Validates the type field of a Service."""
        s_type = service_type
        if s_type is None or s_type not in [r.value for r in ServiceType]:
            raise ServiceException(f"Invalid service type: {s_type}.")
        return s_type


class Service(Object):
    """Service template."""
    kind: str = Field(default="Service", validate_default=True)
    metadata: ServiceMeta = Field(default=ServiceMeta(), validate_default=True)
    spec: ServiceSpec = Field(default=ServiceSpec(), validate_default=True)
    status: ServiceStatus = Field(default=ServiceStatus(),
                                  validate_default=True)

    def get_namespace(self):
        """Returns the namespace of a Service."""
        return self.metadata.namespace # pylint: disable=no-member


class ServiceList(ObjectList):
    """List of Services."""
    kind: str = Field(default="ServiceList")


# Testing purposes.
if __name__ == "__main__":
    print(ServiceList())
