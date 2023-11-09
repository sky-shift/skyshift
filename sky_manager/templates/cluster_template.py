from enum import Enum
import time
from typing import Dict, List

from sky_manager.templates.object_template import Object, ObjectException, \
    ObjectList, ObjectMeta, ObjectSpec, ObjectStatus
from sky_manager.templates.resource_template import ResourceEnum


class ClusterStatusEnum(Enum):
    # Setting up cluster.
    INIT = "INIT"
    # Cluster is ready to accept jobs.
    READY = "READY"
    # Cluster is in error state.
    # This state is reached when the cluster fails several heartbeats or is not a valid cluster.
    ERROR = "ERROR"

    def __eq__(self, other):
        if isinstance(other, str):
            return self.value == other
        return super().__eq__(other)


class ClusterException(ObjectException):
    """Raised when the cluster dict is invalid."""

    def __init__(self, message: str = 'Failed to create cluster.'):
        super().__init__(message)


class ClusterStatus(ObjectStatus):

    def __init__(self,
                 conditions: List[Dict[str, str]] = [],
                 status: str = ClusterStatusEnum.INIT.value,
                 capacity: Dict[str, Dict[ResourceEnum, float]] = {},
                 allocatable_capacity: Dict[str, Dict[ResourceEnum,
                                                      float]] = {}):
        if not conditions:
            cur_time = time.time()
            conditions = [{
                'status': ClusterStatusEnum.INIT.value,
                'createTime': str(cur_time),
                'updateTime': str(cur_time),
            }]
        if not status:
            status = ClusterStatusEnum.INIT.value
        super().__init__(conditions, status)
        self.capacity = capacity
        self.allocatable_capacity = allocatable_capacity

        self._verify_conditions(self.conditions)
        self._verify_status(self.curStatus)
        self._verify_capacity(self.capacity)
        self._verify_capacity(self.allocatable_capacity)

    def _verify_capacity(self, capacity: Dict[str, Dict[ResourceEnum, float]]):
        res_emum_dict = {m.name: m.value for m in ResourceEnum}
        for node_name, node_resources in capacity.items():
            keys_in_enum = set(node_resources.keys()).issubset(
                res_emum_dict.values())
            if not keys_in_enum:
                raise ClusterException(
                    f'Invalid resource specification for node {node_name}: {node_resources}. '
                    'Please use ResourceEnum to specify resources.')

    def _verify_conditions(self, conditions: List[Dict[str, str]]):
        if len(conditions) == 0:
            raise ClusterException(
                'Cluster status\'s condition field is empty.')
        for condition in conditions:
            if 'status' not in condition:
                raise ClusterException(
                    'Cluster status\'s condition field is missing status.')

    def _verify_status(self, status: str):
        if status is None or status not in ClusterStatusEnum.__members__:
            raise ClusterException(f'Invalid cluster status: {status}.')

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

    def update_capacity(self, capacity: Dict[str, Dict[ResourceEnum, float]]):
        self._verify_capacity(capacity)
        self.capacity = capacity

    def update_allocatable_capacity(self, capacity: Dict[str,
                                                         Dict[ResourceEnum,
                                                              float]]):
        self._verify_capacity(capacity)
        self.allocatable_capacity = capacity

    @staticmethod
    def from_dict(config: dict):
        conditions = config.pop('conditions', [])
        status = config.pop('status', None)
        capacity = config.pop('capacity', {})
        allocatable_capacity = config.pop('allocatable', {})
        assert not config, f'Config contains extra fields, {config}.'

        cluster_status = ClusterStatus(
            conditions=conditions,
            status=status,
            capacity=capacity,
            allocatable_capacity=allocatable_capacity)
        return cluster_status

    def __iter__(self):
        cluster_dict = dict(super().__iter__())
        cluster_dict.update({
            'allocatable': self.allocatable_capacity,
            'capacity': self.capacity,
        })
        yield from cluster_dict.items()


class ClusterMeta(ObjectMeta):
    pass


class ClusterSpec(ObjectSpec):

    def __init__(self, manager: str):
        self.manager = manager
        self._verify_manager(manager)
        super().__init__()

    def _verify_manager(self, manager: str):
        if manager is None:
            raise ClusterException('Cluster spec is missing manager specs.')

    def __iter__(self):
        yield from {
            'manager': self.manager,
        }.items()

    @staticmethod
    def from_dict(config: dict):
        manager = config.pop('manager', None)
        assert manager is not None, 'Cluster spec\'s manager field is empty.'
        return ClusterSpec(manager)


class Cluster(Object):

    def __init__(self, meta: dict = {}, spec: dict = {}, status: dict = {}):
        super().__init__(meta, spec, status)
        self.meta = ClusterMeta.from_dict(meta)
        self.spec = ClusterSpec.from_dict(spec)
        self.status = ClusterStatus.from_dict(status)

    def get_status(self):
        return self.status.curStatus

    @staticmethod
    def from_dict(config: dict):
        assert config['kind'] == 'Cluster', 'Not a Cluster object: {}'.format(
            config)

        meta = config.pop('metadata', {})
        spec = config.pop('spec', {})
        status = config.pop('status', {})

        cluster_obj = Cluster(meta=meta, spec=spec, status=status)
        return cluster_obj

    def __iter__(self):
        yield from {
            'kind': 'Cluster',
            'metadata': dict(self.meta),
            'spec': dict(self.spec),
            'status': dict(self.status),
        }.items()


class ClusterList(ObjectList):

    def __iter__(self):
        list_dict = dict(super().__iter__())
        list_dict['kind'] = 'ClusterList'
        yield from list_dict.items()

    @staticmethod
    def from_dict(config: dict):
        assert config[
            'kind'] == 'ClusterList', "Not a ClusterList object: {}".format(
                config)
        cluster_list = []
        for cluster_dict in config['items']:
            cluster_list.append(Cluster.from_dict(cluster_dict))
        return ClusterList(cluster_list)
