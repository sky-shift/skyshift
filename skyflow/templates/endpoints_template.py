"""
Endpoints template.
"""
from typing import Dict, Optional

from pydantic import BaseModel, Field, field_validator

from skyflow.templates.object_template import (NamespacedObjectMeta, Object,
                                               ObjectException, ObjectList,
                                               ObjectSpec, ObjectStatus)


class EndpointsException(ObjectException):
    """Raised when the job template is invalid."""


class EndpointsStatus(ObjectStatus):
    """Endpoints status."""


class EndpointsMeta(NamespacedObjectMeta):
    """Endpoints metadata."""


class EndpointObject(BaseModel):
    """Endpoint object representing all endpoints for a cluster."""
    # Num endpoints to make in endpoints yaml of the primary cluster.
    num_endpoints: int = Field(default=0, validate_default=True)
    # This is exposed ip and port on the primary cluster.
    exposed_to_cluster: bool = Field(default=False, validate_default=True)

    @field_validator('num_endpoints')
    @classmethod
    def validate_num_endpoints(cls, num_endpoints: int) -> int:
        """Validates the number of endpoints. The number must be non-negative."""
        if num_endpoints < 0:
            raise ValueError("Number of endpoints must be non-negative.")
        return num_endpoints

    @field_validator('exposed_to_cluster')
    @classmethod
    def validate_exposed_to_cluster(cls, exposed_to_cluster: bool) -> bool:
        """Validates the exposed_to_cluster field. Must be a boolean."""
        if not isinstance(exposed_to_cluster, bool):
            raise ValueError("Exposed to cluster field must be a boolean.")
        return exposed_to_cluster


class EndpointsSpec(ObjectSpec):
    """Endpoints spec."""
    selector: Dict[str, str] = Field(default={}, validate_default=True)
    endpoints: Dict[str, EndpointObject] = Field(default={},
                                                 validate_default=True)
    primary_cluster: Optional[str] = Field(default=None)

    @field_validator('selector')
    @classmethod
    def validate_selector(cls, selector: Dict[str, str]) -> Dict[str, str]:
        """Validates the selector. Ensures all keys and values are strings."""
        if not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in selector.items()):
            raise ValueError("Selector keys and values must be strings.")
        return selector

    @field_validator('endpoints')
    @classmethod
    def validate_endpoints(
            cls, endpoints: Dict[str,
                                 EndpointObject]) -> Dict[str, EndpointObject]:
        """Validates the endpoints. Ensures keys are non empty-strings."""
        if any(not cluster_name for cluster_name in endpoints.keys()):
            raise ValueError(
                "Cluster names in endpoints must be non-empty strings.")
        return endpoints

    @field_validator('primary_cluster')
    @classmethod
    def validate_primary_cluster(
            cls, primary_cluster: Optional[str]) -> Optional[str]:
        """Validates the primary cluster field. If provided, it must be a non-empty string."""
        if primary_cluster == "":
            raise ValueError("Primary cluster cannot be an empty string.")
        return primary_cluster


class Endpoints(Object):
    """Endpoints object."""
    kind: str = Field(default="Endpoints", validate_default=True)
    metadata: EndpointsMeta = Field(default=EndpointsMeta(),
                                    validate_default=True)
    spec: EndpointsSpec = Field(default=EndpointsSpec(), validate_default=True)
    status: EndpointsStatus = Field(default=EndpointsStatus(),
                                    validate_default=True)

    def get_namespace(self):
        """Returns the namespace of the object."""
        return self.metadata.namespace  # pylint: disable=no-member


class EndpointsList(ObjectList):
    """List of Endpoints."""
    kind: str = Field(default="EndpointsList")
