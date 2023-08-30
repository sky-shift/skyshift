# Events for Watcher Class
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
                self.key: self.value
            }
        }.items()

    def __repr__(self):
        return str(dict(self))
