"""
Event template for Skyflow.
"""
import enum
from typing import Generic, TypeVar

from pydantic import BaseModel, Field, field_validator

from skyflow.utils.utils import load_object

GenericType = TypeVar("GenericType")


class WatchEventEnum(enum.Enum):
    """
    Enum for watch event types.
    """
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


class WatchEvent(BaseModel, Generic[GenericType]):
    """Watch event for Skyflow."""
    kind: str = Field(default="WatchEvent")
    event_type: str
    object: GenericType

    @field_validator("event_type")
    @classmethod
    def verify_event_type(cls, event_type: str):
        """Validates the event type field of a WatchEvent."""
        if not any(event_type == ev_enum.value for ev_enum in WatchEventEnum):
            raise ValueError(f"Invalid watch event type, {event_type}.")
        return event_type

    @field_validator("object", mode="before")
    @classmethod
    def set_correct_object_type(cls, value):
        """Converts the object field to the correct type."""
        if isinstance(value, dict):
            return load_object(value)
        return value
