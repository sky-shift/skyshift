import enum

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


class WatchEvent(object):

    def __init__(self, event_type, key, value):
        self.event_type = event_type
        self.key = key
        self.value = value

    def __iter__(self):
        yield from {
            "kind": "WatchEvent",
            'type': self.event_type,
            'object': {
                self.key: dict(self.value)
            }
        }.items()

    def __repr__(self):
        return str(dict(self))
