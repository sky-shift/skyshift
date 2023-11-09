import enum
import time
from typing import Any, Dict, List

from sky_manager.templates.object_template import Object, ObjectException, \
    ObjectList, ObjectMeta, ObjectSpec, ObjectStatus
from sky_manager.templates.job_template import JobStatusEnum
from sky_manager.templates.resource_template import ResourceEnum

DEFAULT_IMAGE = 'nginx:1.14.2'
DEFAULT_JOB_RESOURCES = {
    'cpu': 0.5,
    'gpu': 0,
    'memory': 128,
}
DEFAULT_NAMESPACE = 'default'

# Deployments share similar status as jobs.
class DeploymentStatusEnum(enum.Enum):
    INIT = 'INIT'
    # When job has been scheduled to a cluster.
    SCHEDULED = 'SCHEDULED'
    # When job has been binded to cluster but not scheduled on cluster node yet.
    PENDING = 'PENDING'
    # Includes both setup (such as containercreate/pull) and running.
    RUNNING = 'RUNNING'
    # If job has completed.
    COMPLETED = 'COMPLETED'
    # If job has failed execution on a cluster.
    FAILED = 'FAILED'
    # If a job has been evicted from the cluster (by the JobExecutionController).
    EVICTED = 'EVICTED'
    # If has job is in a deletion phase.
    DELETED = 'DELETED'


class DeploymentException(Exception):
    "Raised when a deployment config is invalid."
    pass


class DeploymentStatus(ObjectStatus):

    def __init__(self,
                 conditions: List[Dict[str, str]] = [],
                 status: str = DeploymentStatusEnum.INIT.value,
                 clusters: dict = {}):
        if not conditions:
            cur_time = time.time()
            conditions = [{
                'status': DeploymentStatusEnum.INIT.value,
                'createTime': str(cur_time),
                'updateTime': str(cur_time),
            }]
        if status is None:
            status = DeploymentStatusEnum.INIT.value
        super().__init__(conditions, status)

        self.clusters = clusters
        self._verify_conditions(self.conditions)
        self._verify_status(self.curStatus)

    def _verify_conditions(self, conditions: List[Dict[str, str]]):
        if len(conditions) == 0:
            raise DeploymentException('Deployment status\'s condition field is empty.')
        for condition in conditions:
            if 'status' not in condition:
                raise DeploymentException(
                    'Deployment status\'s condition field is missing status.')

    def _verify_status(self, status: str):
        if status is None or status not in DeploymentStatusEnum.__members__:
            raise DeploymentException(f'Invalid deployment status: {status}.')

    def update_conditions(self, conditions):
        self._verify_conditions(conditions)
        self.conditions = conditions

    def update_clusters(self, clusters: str):
        self.clusters = clusters

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
        clusters = config.pop('clusters', {})
        assert not config, f'Config contains extra fields, {config}.'

        return DeploymentStatus(conditions=conditions,
                               status=status,
                               cluster=clusters)

    def __iter__(self):
        job_dict = dict(super().__iter__())
        job_dict.update({
            'cluster': self.cluster,
        })
        yield from job_dict.items()


class DeploymentMeta(ObjectMeta):

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
        return DeploymentMeta(name=name,
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


class DeploymentSpec(ObjectSpec):

    def __init__(self,
                 image: str = DEFAULT_IMAGE,
                 resources: Dict[str, Any] = DEFAULT_JOB_RESOURCES,
                 run: str = ""):
        super().__init__()
        self.image = image
        self.resources = resources
        self.run = run

        self._verify_resources(self.resources)

    def _verify_resources(self, resources: Dict[str, Any]):
        res_emum_dict = {m.name: m.value for m in ResourceEnum}
        keys_in_enum = set(resources.keys()).issubset(res_emum_dict.values())
        if not keys_in_enum:
            raise DeploymentException(f'Invalid resource specification: {resources}. '
                               'Please use ResourceEnum to specify resources.')

    def __iter__(self):
        yield from {
            'image': self.image,
            'resources': dict(self.resources),
            'run': self.run,
        }.items()

    @staticmethod
    def from_dict(config: dict):
        image = config.pop('image', DEFAULT_IMAGE)
        resources = config.pop('resources', DEFAULT_JOB_RESOURCES)
        run = config.pop('run', "")
        assert not config, f'Config contains extra fields, {config}.'
        return DeploymentSpec(image=image, resources=resources, run=run)


class Deployment(Object):

    def __init__(self, meta: dict = {}, spec: dict = {}, status: dict = {}):
        super().__init__(meta, spec, status)
        self.meta = DeploymentMeta.from_dict(meta)
        self.spec = DeploymentSpec.from_dict(spec)
        self.status = DeploymentStatus.from_dict(status)

    def get_status(self):
        return self.status.curStatus

    @staticmethod
    def from_dict(config: dict):
        assert config['kind'] == 'Job', 'Not a Job object: {}'.format(config)

        meta = config.pop('metadata', {})
        spec = config.pop('spec', {})
        status = config.pop('status', {})

        return Deployment(meta=meta, spec=spec, status=status)

    def __iter__(self):
        yield from {
            'kind': 'Deployment',
            'metadata': dict(self.meta),
            'spec': dict(self.spec),
            'status': dict(self.status),
        }.items()


class DeploymentList(ObjectList):

    def __iter__(self):
        list_dict = dict(super().__iter__())
        list_dict['kind'] = 'DeploymentList'
        yield from list_dict.items()

    @staticmethod
    def from_dict(config: dict):
        assert config['kind'] == 'DeploymentList', "Not a JobList object: {}".format(
            config)
        job_list = []
        for job_dict in config['items']:
            job_list.append(Deployment.from_dict(job_dict))
        return DeploymentList(job_list)