import enum
import time
from typing import Any, Dict, List

from sky_manager.templates.object_template import Object, ObjectException, \
    ObjectList, ObjectMeta, ObjectSpec, ObjectStatus
from sky_manager.templates.resource_template import ResourceEnum

DEFAULT_IMAGE = 'ubuntu:latest'
DEFAULT_JOB_RESOURCES = {
    'cpu': 1,
    'gpu': 0,
    'memory': 128,
}
DEFAULT_NAMESPACE = 'default'


class JobStatusEnum(enum.Enum):
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

    def __eq__(self, other):
        if isinstance(other, str):
            return self.value == other
        return super().__eq__(other)

class JobException(Exception):
    "Raised when the job config is invalid."
    pass


class JobStatus(ObjectStatus):

    def __init__(self,
                 conditions: List[Dict[str, str]] = [],
                 status: str = JobStatusEnum.INIT.value,
                 clusters: Dict[str, int] = {}):
        if not conditions:
            cur_time = time.time()
            conditions = [{
                'status': JobStatusEnum.INIT.value,
                'createTime': str(cur_time),
                'updateTime': str(cur_time),
            }]
        if status is None:
            status = JobStatusEnum.INIT.value
        super().__init__(conditions, status)

        self.clusters = clusters
        self._verify_conditions(self.conditions)
        self._verify_status(self.curStatus)

    def _verify_conditions(self, conditions: List[Dict[str, str]]):
        if len(conditions) == 0:
            raise JobException('Job status\'s condition field is empty.')
        for condition in conditions:
            if 'status' not in condition:
                raise JobException(
                    'Job status\'s condition field is missing status.')

    def _verify_status(self, status: str):
        if status is None or status not in JobStatusEnum.__members__:
            raise JobException(f'Invalid job status: {status}.')

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
        clusters = config.pop('clusters', None)
        assert not config, f'Config contains extra fields, {config}.'

        job_status = JobStatus(conditions=conditions,
                               status=status,
                               clusters=clusters)
        return job_status

    def __iter__(self):
        job_dict = dict(super().__iter__())
        job_dict.update({
            'clusters': self.clusters,
        })
        yield from job_dict.items()


class JobMeta(ObjectMeta):

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
        return JobMeta(name=name,
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


class JobSpec(ObjectSpec):

    def __init__(self,
                 image: str = DEFAULT_IMAGE,
                 resources: Dict[str, Any] = DEFAULT_JOB_RESOURCES,
                 replicas: int = 1,
                 run: str = "",):
        super().__init__()
        self.image = image
        self.resources = resources
        self.run = run
        self.replicas = replicas
        assert self.replicas > 0, f'Invalid replicas: {self.replicas}.'

        self._verify_resources(self.resources)

    def _verify_resources(self, resources: Dict[str, Any]):
        res_emum_dict = {m.name: m.value for m in ResourceEnum}
        keys_in_enum = set(resources.keys()).issubset(res_emum_dict.values())
        if not keys_in_enum:
            raise JobException(f'Invalid resource specification: {resources}. '
                               'Please use ResourceEnum to specify resources.')

    def __iter__(self):
        yield from {
            'image': self.image,
            'resources': dict(self.resources),
            'run': self.run,
            'replicas': self.replicas,
        }.items()

    @staticmethod
    def from_dict(config: dict):
        image = config.pop('image', DEFAULT_IMAGE)
        resources = config.pop('resources', DEFAULT_JOB_RESOURCES)
        run = config.pop('run', "")
        replicas = config.pop('replicas', 1)
        assert not config, f'Config contains extra fields, {config}.'
        return JobSpec(image=image, resources=resources, run=run, replicas=replicas)


class Job(Object):

    def __init__(self, meta: dict = {}, spec: dict = {}, status: dict = {}):
        super().__init__(meta, spec, status)
        self.meta = JobMeta.from_dict(meta)
        self.spec = JobSpec.from_dict(spec)
        self.status = JobStatus.from_dict(status)

    def get_status(self):
        return self.status.curStatus

    @staticmethod
    def from_dict(config: dict):
        assert config['kind'] == 'Job', 'Not a Job object: {}'.format(config)

        meta = config.pop('metadata', {})
        spec = config.pop('spec', {})
        status = config.pop('status', {})

        obj = Job(meta=meta, spec=spec, status=status)
        return obj

    def __iter__(self):
        yield from {
            'kind': 'Job',
            'metadata': dict(self.meta),
            'spec': dict(self.spec),
            'status': dict(self.status),
        }.items()


class JobList(ObjectList):

    def __iter__(self):
        list_dict = dict(super().__iter__())
        list_dict['kind'] = 'JobList'
        yield from list_dict.items()

    @staticmethod
    def from_dict(config: dict):
        assert config['kind'] == 'JobList', "Not a JobList object: {}".format(
            config)
        job_list = []
        for job_dict in config['items']:
            job_list.append(Job.from_dict(job_dict))
        return JobList(job_list)