import uuid
from typing import Dict, Generic, List, TypeVar

from pydantic import BaseModel, Field, field_validator, model_validator

from skyflow.utils.utils import load_object

T = TypeVar('T')


class ObjectException(Exception):

    def __init__(self, message='Failed to create object.'):
        self.message = message
        super().__init__(self.message)


class ObjectStatus(BaseModel):
    conditions: List[Dict[str, str]] = Field(default=[])

    def update_conditions(self, conditions):
        self.conditions = conditions


class ObjectMeta(BaseModel, validate_assignment=True):
    name: str = Field(default=uuid.uuid4().hex[:16], validate_default=True)
    labels: Dict[str, str] = Field(default={})
    annotations: Dict[str, str] = Field(default={})
    # ETCD resource version for an object.
    resource_version: int = Field(default=-1)

    @field_validator('name')
    @classmethod
    def verify_name(cls, v: str) -> str:
        if not v:
            raise ValueError('Object name cannot be empty.')
        return v


class ObjectSpec(BaseModel):
    pass


class Object(BaseModel):
    kind: str = Field(default='Object')
    metadata: ObjectMeta = Field(default=ObjectMeta())
    spec: ObjectSpec = Field(default=ObjectSpec())
    status: ObjectStatus = Field(default=ObjectStatus())

    @model_validator(mode='before')
    def set_kind(cls, values):
        if isinstance(values, Object):
            return values
        values['kind'] = cls.__name__
        return values

    def get_status(self):
        return self.status.status

    def get_name(self):
        return self.metadata.name


class ObjectList(BaseModel, Generic[T]):
    kind: str = Field(default='ObjectList')
    objects: List[T] = Field(default=[])

    @model_validator(mode='before')
    def set_kind(cls, values):
        values['kind'] = cls.__name__
        return values

    @field_validator('objects', mode='before')
    def set_correct_object_type(cls, v):
        for idx, obj in enumerate(v):
            if isinstance(obj, dict):
                v[idx] = load_object(obj)
        return v

    def add_object(self, obj: T):
        self.objects.append(obj)
