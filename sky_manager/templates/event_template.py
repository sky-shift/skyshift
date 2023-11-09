import enum

from sky_manager.templates import Object
from sky_manager.utils.utils import generate_object

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


class WatchEvent:

    def __init__(self, event_type: str, object: Object):
        self.event_type = event_type
        self.object = object

        self._verify_event_type(event_type)
    
    def _verify_event_type(self, event_type: str):
        if not any(event_type == ev_enum.value for ev_enum in WatchEventEnum):
            raise ValueError(f'Invalid watch event type, {event_type}.')

    def __iter__(self):
        yield from {
            "kind": "WatchEvent",
            'type': self.event_type,
            'object': dict(self.object)
        }.items()
    
    @staticmethod
    def from_dict(config: dict):
        assert config['kind'] == 'WatchEvent', f'Not a WatchEvent object: {config}'

        event_type = config.pop('type', None)
        obj_dict = config.pop('object', None)
        obj =  generate_object(obj_dict)
        return WatchEvent(event_type, obj)

    def __repr__(self):
        return str(dict(self))
