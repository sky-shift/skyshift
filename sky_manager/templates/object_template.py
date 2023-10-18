from typing import Dict, List


class ObjectException(Exception):

    def __init__(self, message='Failed to create object.'):
        self.message = message
        super().__init__(self.message)


class ObjectStatus(object):

    def __init__(self,
                 conditions: List[Dict[str, str]] = [],
                 status: str = None):
        self.conditions = conditions
        self.curStatus = status

    def update_conditions(self, conditions):
        self.conditions = conditions

    def update_status(self, status: str):
        self.curStatus = status

    @staticmethod
    def from_dict(config: dict):
        conditions = config.pop('conditions', [])
        status = config.pop('status', None)
        return ObjectStatus(conditions, status)

    def __iter__(self):
        yield from {
            'conditions': self.conditions,
            'status': self.curStatus,
        }.items()

    def __repr__(self):
        return str(dict(self))


class ObjectMeta(object):

    def __init__(self,
                 name=str,
                 labels=Dict[str, str],
                 annotations=Dict[str, str]):
        assert name is not None, "Object name cannot be None."
        self.name = name
        self.labels = labels
        self.annotations = annotations

    @staticmethod
    def from_dict(config):
        name = config.pop('name', None)
        labels = config.pop('labels', {})
        annotations = config.pop('annotations', {})
        return ObjectMeta(name, labels, annotations)

    def __iter__(self):
        yield from {
            'name': self.name,
            'labels': self.labels,
            'annotations': self.annotations,
        }.items()

    def __repr__(self):
        return str(dict(self))


class ObjectSpec(object):

    def __init__(self):
        pass

    @staticmethod
    def from_dict(config):
        pass

    def __iter__(self):
        yield from {}.items()

    def __repr__(self):
        return str(dict(self))


class Object(object):

    def __init__(self, meta: dict = {}, spec: dict = {}, status: dict = {}):
        self.meta = meta
        self.spec = spec
        self.status = status

    @staticmethod
    def from_dict(config: dict):
        meta = config.pop('metadata', {})
        spec = config.pop('spec', {})
        status = config.pop('status', {})
        return Object(meta=meta, spec=spec, status=status)

    def __iter__(self):
        yield from {
            'kind': 'Object',
            'metadata': self.meta,
            'spec': self.spec,
            'status': self.status,
        }.items()

    def __repr__(self):
        return str(dict(self))


class ObjectList(object):

    def __init__(self, objects=List[Object]):
        self.objects = objects

    def __iter__(self):
        yield from {
            'kind': 'ObjectList',
            'items': [dict(j) for j in self.objects],
        }.items()

    @staticmethod
    def from_dict(config):
        pass

    def __repr__(self):
        return str(dict(self))