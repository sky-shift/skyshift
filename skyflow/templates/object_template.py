"""
Object template.
"""
import re
import uuid
from typing import Dict, Generic, List, TypeVar

from pydantic import BaseModel, Field, field_validator, model_validator

from skyflow.utils.utils import load_object

GenericType = TypeVar("GenericType")


class ObjectException(Exception):
    """Raised when the object dict is invalid."""

    def __init__(self, message="Failed to create object."):
        self.message = message
        super().__init__(self.message)


class ObjectStatus(BaseModel):
    """Status of an object."""
    conditions: List[Dict[str, str]] = Field(default=[], validate_default=True)

    def update_conditions(self, conditions):
        """Updates the conditions field of an object."""
        self.conditions = conditions


class ObjectMeta(BaseModel, validate_assignment=True):
    """Metadata of an object."""
    name: str = Field(default=uuid.uuid4().hex[:16], validate_default=True)
    labels: Dict[str, str] = Field(default={})
    annotations: Dict[str, str] = Field(default={})
    # ETCD resource version for an object.
    resource_version: int = Field(default=-1)

    @field_validator("name")
    @classmethod
    def verify_name(cls, value: str) -> str:
        """
        Validates if the provided name is a valid Skyflow object name.
        Skyflow object names must:
        - contain only lowercase alphanumeric characters or '-'
        - start and end with an alphanumeric character
        - be no more than 63 characters long
        """
        name = value
        if not name:
            raise ValueError("Object name cannot be empty.")
        pattern = r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?$'
        match = bool(re.match(pattern, name)) and len(name) <= 63
        if match:
            return name
        # Regex failed
        raise ValueError(("Invalid object name. Object names must follow "
                          f"regex pattern, {pattern}, and must be no more "
                          "than 63 characters long."))


class NamespacedObjectMeta(ObjectMeta):
    """Metadata of a Namespaced Object."""
    namespace: str = Field(default='default', validate_default=True)

    @field_validator("namespace")
    @classmethod
    def verify_namespace(cls, value: str) -> str:
        """Validates the namespace field of a Service."""
        if not value:
            raise ValueError("Namespace cannot be empty.")
        return value


class ObjectSpec(BaseModel):
    """Spec of an object."""


class Object(BaseModel):
    """Object template."""
    kind: str = Field(default="Object")
    metadata: ObjectMeta = Field(default=ObjectMeta())
    spec: ObjectSpec = Field(default=ObjectSpec())
    status: ObjectStatus = Field(default=ObjectStatus())

    @model_validator(mode="before")
    @classmethod
    def set_kind(cls, values):
        """Sets the kind field of an object."""
        if isinstance(values, Object):
            return values
        values["kind"] = cls.__name__
        return values

    def get_status(self):
        """Returns the status of an object."""
        return self.status.status  # pylint: disable=no-member

    def get_name(self):
        """Returns the name of an object."""
        return self.metadata.name  # pylint: disable=no-member


class ObjectList(BaseModel, Generic[GenericType]):
    """List of objects."""
    kind: str = Field(default="ObjectList")
    objects: List[GenericType] = Field(default=[])

    @model_validator(mode="before")
    @classmethod
    def set_kind(cls, values):
        """Sets the kind field of an object."""
        values["kind"] = cls.__name__
        return values

    @field_validator("objects", mode="before")
    @classmethod
    def set_correct_object_type(cls, value):
        """Sets the correct object type."""
        for idx, obj in enumerate(value):
            if isinstance(obj, dict):
                value[idx] = load_object(obj)
        return value

    def add_object(self, obj: GenericType):
        """Adds an object to the list."""
        self.objects.append(obj)  # pylint: disable=no-member
