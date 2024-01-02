import enum

from pydantic import BaseModel, Field, field_validator, validator, model_validator, root_validator

from typing import Union
from skyflow.templates import *
from skyflow.utils.utils import load_object
from skyflow.templates.service_template import Service
from skyflow.templates.endpoints_template import Endpoints
class WatchEventEnum(enum.Enum):
    # New object is added.
    ADD = "ADD"
    # An existing object is modified.
    UPDATE = "UPDATE"
    # An object is deleted.
    DELETE = "DELETE"

    def __eq__(self, other):
        if isinstance(other, str):
            return self.value == other
        return super().__eq__(other)


class WatchEvent(BaseModel):
    kind: str = Field(default='WatchEvent')
    event_type: str
    object: Union[Cluster, Job, FilterPolicy, Namespace, Link, Service, Endpoints, Object]
    
    @field_validator('event_type')
    @classmethod    
    def verify_event_type(cls, event_type: str):
        if not any(event_type == ev_enum.value for ev_enum in WatchEventEnum):
            raise ValueError(f'Invalid watch event type, {event_type}.')
        return event_type

    @field_validator('object', mode='before')
    def set_correct_object_type(cls, v):
        if isinstance(v, dict):
            return load_object(v)
        return v

