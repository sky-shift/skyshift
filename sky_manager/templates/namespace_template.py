from enum import Enum
import time
from typing import Dict, List

from sky_manager.templates.object_template import Object, ObjectException, \
    ObjectList, ObjectMeta, ObjectSpec, ObjectStatus
from sky_manager.templates.resource_template import ResourceEnum


class NamespaceEnum(Enum):
    # Namespace is active.
    READY = "READY"


class NamespaceException(ObjectException):
    """Raised when the namespace dict is invalid."""

    def __init__(self, message: str = 'Failed to create namespace.'):
        super().__init__(message)


class NamespaceStatus(ObjectStatus):

    def __init__(self,
                 conditions: List[Dict[str, str]] = [],
                 status: str = NamespaceEnum.READY.value):
        if not conditions:
            cur_time = time.time()
            conditions = [{
                'status': NamespaceEnum.READY.value,
                'createTime': str(cur_time),
                'updateTime': str(cur_time),
            }]
        if not status:
            status = NamespaceEnum.READY.value
        super().__init__(conditions, status)

        self._verify_conditions(self.conditions)
        self._verify_status(self.curStatus)

    def _verify_conditions(self, conditions: List[Dict[str, str]]):
        if len(conditions) == 0:
            raise NamespaceException(
                'Namespace status\'s condition field is empty.')
        for condition in conditions:
            if 'status' not in condition:
                raise NamespaceException(
                    'Namespace status\'s condition field is missing status.')

    def _verify_status(self, status: str):
        if status is None or status not in NamespaceEnum.__members__:
            raise NamespaceException(f'Invalid namespace status: {status}.')

    def update_conditions(self, conditions):
        self._verify_conditions(conditions)
        self.conditions = conditions

    def update_status(self, status: str):
        self._verify_status(status)
        self.curStatus = status
        # Check most recent status of the cluster.
        previous_status = self.conditions[-1]
        if previous_status['status'] == status:
            previous_status['updateTime'] = time.time()
        else:
            cur_time = time.time()
            self.conditions.append({
                'status': status,
                'createTime': str(cur_time),
                'updateTime': str(cur_time),
            })
            self.curStatus = status

    @staticmethod
    def from_dict(config: dict):
        conditions = config.pop('conditions', [])
        status = config.pop('status', None)
        assert not config, f'Config contains extra fields, {config}.'

        return NamespaceStatus(conditions=conditions, status=status)


class NamespaceMeta(ObjectMeta):
    pass


class NamespaceSpec(ObjectSpec):
    pass


class Namespace(Object):

    def __init__(self, meta: dict = {}, spec: dict = {}, status: dict = {}):
        super().__init__(meta, spec, status)
        self.meta = NamespaceMeta.from_dict(meta)
        self.spec = NamespaceSpec.from_dict(spec)
        self.status = NamespaceStatus.from_dict(status)

    @staticmethod
    def from_dict(config: dict):
        assert config[
            'kind'] == 'Namespace', 'Not a namespace object: {}'.format(config)

        meta = config.pop('metadata', {})
        spec = config.pop('spec', {})
        status = config.pop('status', {})

        return Namespace(meta=meta, spec=spec, status=status)

    def __iter__(self):
        yield from {
            'kind': 'Namespace',
            'metadata': dict(self.meta),
            'spec': dict(self.spec),
            'status': dict(self.status),
        }.items()


class NamespaceList(ObjectList):

    def __iter__(self):
        list_dict = dict(super().__iter__())
        list_dict['kind'] = 'NamespaceList'
        yield from list_dict.items()

    @staticmethod
    def from_dict(config: dict):
        assert config[
            'kind'] == 'NamespaceList', "Not a NamespaceList object: {}".format(
                config)
        obj_list = []
        for obj_dict in config['items']:
            obj_list.append(Namespace.from_dict(obj_dict))
        return NamespaceList(obj_list)
