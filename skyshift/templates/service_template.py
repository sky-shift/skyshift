"""Service template for SkyShift."""
import enum
import ipaddress
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from skyshift.templates.object_template import (NamespacedObjectMeta, Object,
                                                ObjectException, ObjectList,
                                                ObjectSpec, ObjectStatus)


class ServiceType(enum.Enum):
    """Enum for Service type."""
    ClusterIP = "ClusterIP"  # pylint: disable=invalid-name
    LoadBalancer = "LoadBalancer"  # pylint: disable=invalid-name
    ExternalName = "ExternalName"  # pylint: disable=invalid-name

    def __eq__(self, other):
        if isinstance(other, str):
            return self.value == other
        return super().__eq__(other)

    @classmethod
    def has_value(cls, value):
        """
        Checks if the specified value is present among the enum values.
        """
        return any(value == item.value for item in cls)


class ServiceException(ObjectException):
    """Raised when the job template is invalid."""


class ServiceStatus(ObjectStatus):
    """Status of a Service."""
    external_ip: Optional[str] = Field(default=None)


class ServiceMeta(NamespacedObjectMeta):
    """Metadata of a Service."""


class ServicePorts(BaseModel):
    """Ports of a Service."""
    port: int = Field(default=None, validate_default=True)
    target_port: int = Field(default=None, validate_default=True)
    protocol: str = Field(default="TCP", validate_default=True)


class ServiceSpec(ObjectSpec):
    """Spec of a Service."""
    type: str = Field(default=ServiceType.ClusterIP.value,
                      validate_default=True)
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
            raise ValueError(f"Invalid service type: {s_type}.")
        return s_type

    @field_validator('ports')
    @classmethod
    def verify_ports(cls,
                     service_ports: List[ServicePorts]) -> List[ServicePorts]:
        """Validates each service_port in the ports field."""
        for service_port in service_ports:
            if not 0 < service_port.port <= 65535:
                raise ValueError(f"Invalid port number: {service_port.port}")
            if not 0 < service_port.target_port <= 65535:
                raise ValueError(
                    f"Invalid target port number: {service_port.target_port}")
            if service_port.protocol not in ["TCP", "UDP"]:
                raise ValueError(
                    f"Unsupported protocol: {service_port.protocol}")
        return service_ports

    @field_validator('cluster_ip')
    @classmethod
    def validate_cluster_ip(cls, ip_address: str) -> str:
        """Validates the cluster IP address."""
        if ip_address is not None and ip_address != "":
            try:
                ipaddress.IPv4Address(ip_address)
            except ipaddress.AddressValueError as error:
                raise ValueError(
                    f"Invalid IPv4 address: {ip_address}") from error
        return ip_address


class Service(Object):
    """Service template."""
    kind: str = Field(default="Service", validate_default=True)
    metadata: ServiceMeta = Field(default=ServiceMeta(), validate_default=True)
    spec: ServiceSpec = Field(default=ServiceSpec(), validate_default=True)
    status: ServiceStatus = Field(default=ServiceStatus(),
                                  validate_default=True)

    def get_namespace(self):
        """Returns the namespace of a Service."""
        return self.metadata.namespace  # pylint: disable=no-member


class ServiceList(ObjectList):
    """List of Services."""
    kind: str = Field(default="ServiceList")


# Testing purposes.
if __name__ == "__main__":
    print(ServiceList())
