import time
from typing import Any, Dict, List

from sky_manager.templates.object_template import Object, ObjectException, \
    ObjectList, ObjectMeta, ObjectSpec, ObjectStatus

DEFAULT_NAMESPACE = 'default'


class FilterPolicyException(ObjectException):
    "Raised when the job config is invalid."
    pass


class FilterPolicyStatus(ObjectStatus):

    def __init__(self,
                 conditions: List[Dict[str, str]] = [],
                 status: str = 'READY'):
        if not conditions:
            cur_time = time.time()
            conditions = [{
                'status': 'READY',
                'createTime': str(cur_time),
                'updateTime': str(cur_time),
            }]
        if status is None:
            status = 'READY'
        super().__init__(conditions, status)

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

        obj_status = FilterPolicyStatus(conditions=conditions, status=status)
        return obj_status


class FilterPolicyMeta(ObjectMeta):

    def __init__(self,
                 name: str,
                 labels: Dict[str, str] = {},
                 annotations: Dict[str, str] = {},
                 namespace: str = None):
        super().__init__(name, labels, annotations)
        if not namespace:
            namespace = DEFAULT_NAMESPACE
        self.namespace = namespace

    @staticmethod
    def from_dict(config):
        name = config.pop('name', None)
        labels = config.pop('labels', {})
        annotations = config.pop('annotations', {})
        namespace = config.pop('namespace', None)
        return FilterPolicyMeta(name=name,
                                labels=labels,
                                annotations=annotations,
                                namespace=namespace)

    def __iter__(self):
        yield from {
            'name': self.name,
            'labels': self.labels,
            'annotations': self.annotations,
            'namespace': self.namespace,
        }.items()


class ClusterFilter(object):

    def __init__(self, include: List[str] = [], exclude: List[str] = []):
        self.include = []
        self.exclude = []

    def __iter__(self):
        yield from {
            'include': self.include,
            'exclude': self.exclude,
        }.items()

    @staticmethod
    def from_dict(config: dict):
        include = config.pop('include', [])
        exclude = config.pop('exclude', [])
        assert not config, f'Config contains extra fields, {config}.'
        return ClusterFilter(include=include, exclude=exclude)


class FilterPolicySpec(ObjectSpec):

    def __init__(self,
                 cluster_filter: ClusterFilter = None,
                 labels_selector: Dict[str, str] = {}):
        super().__init__()
        if cluster_filter is None:
            cluster_filter = ClusterFilter()
        self.cluster_filter = cluster_filter
        # Name, object_type, and labels are options.
        # TODO(mluo): Make this into a class.
        self.labels_selector = labels_selector

    def __iter__(self):
        yield from {
            'clusterFilter': dict(self.cluster_filter),
            'labelsSelector': self.labels_selector,
        }.items()

    @staticmethod
    def from_dict(config: dict):
        cluster_filter = config.pop('clusterFilter', dict(ClusterFilter()))
        selector = config.pop('labelsSelector', {})
        assert not config, f'Config contains extra fields, {config}.'
        return FilterPolicySpec(cluster_filter=cluster_filter,
                                labels_selector=selector)


class FilterPolicy(Object):

    def __init__(self, meta: dict = {}, spec: dict = {}, status: dict = {}):
        super().__init__(meta, spec, status)
        self.meta = FilterPolicyMeta.from_dict(meta)
        self.spec = FilterPolicySpec.from_dict(spec)
        self.status = FilterPolicyStatus.from_dict(status)

    @staticmethod
    def from_dict(config: dict):
        assert config[
            'kind'] == 'FilterPolicy', 'Not a FilterPolicy object: {}'.format(
                config)

        meta = config.pop('metadata', {})
        spec = config.pop('spec', {})
        status = config.pop('status', {})

        obj = FilterPolicy(meta=meta, spec=spec, status=status)
        return obj

    def __iter__(self):
        yield from {
            'kind': 'FilterPolicy',
            'metadata': dict(self.meta),
            'spec': dict(self.spec),
            'status': dict(self.status),
        }.items()


class FilterPolicyList(ObjectList):

    def __iter__(self):
        list_dict = dict(super().__iter__())
        list_dict['kind'] = 'FilterPolicyList'
        yield from list_dict.items()

    @staticmethod
    def from_dict(config: dict):
        assert config[
            'kind'] == 'FilterPolicyList', "Not a FilterPolicyList object: {}".format(
                config)
        obj_list = []
        for obj_dict in config['items']:
            obj_list.append(FilterPolicy.from_dict(obj_dict))
        return FilterPolicyList(obj_list)