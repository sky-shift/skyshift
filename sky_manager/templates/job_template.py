import enum
import time
from typing import Any, Dict, List

from pydantic import Field, field_validator

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

class JobException(ObjectException):
    """Raised when the job template is invalid."""
    pass

class JobStatus(ObjectStatus):
    conditions: List[Dict[str, str]] = Field(default=[], validate_default=True)
    status: str = Field(default=JobStatusEnum.INIT.value, validate_default=True)
    # Maps clusters to # of replicas. Assigned by scheduler.
    clusters: Dict[str, int] = Field(default={}, validate_default=True)
    # Maps clusters to status of replicas.
    # Job-IDs for each set of replicas per cluster.
    job_ids: Dict[str, str] = Field(default={}, validate_default=True)

    @field_validator('conditions')
    @classmethod
    def verify_conditions(cls, conditions: List[Dict[str, str]]):
        if not conditions:
            conditions = [{
                'status': JobStatusEnum.INIT.value,
                'transitionTime': str(time.time()),
            }]
        if len(conditions) == 0:
            raise JobException('Job status\'s condition field is empty.')
        for condition in conditions:
            if 'status' not in condition:
                raise JobException(
                    'Job status\'s condition field is missing status.')
        return conditions


    @field_validator('status')
    @classmethod
    def verify_status(cls, status: str):
        if status is None or status not in JobStatusEnum.__members__:
            raise JobException(f'Invalid job status: {status}.')
        return status

    def update_conditions(self, conditions):
        self.conditions = conditions

    def update_clusters(self, clusters: str):
        self.clusters = clusters

    def update_status(self, status: str):
        self.status = status
        # Check most recent status of the cluster.
        previous_status = self.conditions[-1]
        if previous_status['status'] != status:
            cur_time = time.time()
            self.conditions.append({
                'status': status,
                'transitionTime': str(cur_time),
            })


class JobMeta(ObjectMeta):
    namespace: str = Field(default=DEFAULT_NAMESPACE, validate_default=True)

    @field_validator('namespace')
    @classmethod
    def verify_namespace(cls, v: str) -> str:
        if not v:
            raise ValueError('Namespace cannot be empty.')
        return v

class JobSpec(ObjectSpec):
    image: str = Field(default=DEFAULT_IMAGE, validate_default=True)
    resources: Dict[str, Any] = Field(default=DEFAULT_JOB_RESOURCES, validate_default=True)
    run: str = Field(default="", validate_default=True)
    replicas: int = Field(default=1, validate_default=True)

    @field_validator('replicas')
    @classmethod
    def verify_replicas(cls, replicas: int) -> int:
        if replicas <= 0:
            raise ValueError(f'Invalid replicas: {replicas}.')
        return replicas

    @field_validator('resources')
    @classmethod
    def verify_resources(cls, resources: Dict[str, Any]):
        res_emum_dict = {m.name: m.value for m in ResourceEnum}
        keys_in_enum = set(resources.keys()).issubset(res_emum_dict.values())
        if not keys_in_enum:
            raise ValueError(f'Invalid spec resource specification: {resources}. '
                               'Please use ResourceEnum to specify resources.')
        return resources


class Job(Object):
    metadata: JobMeta = Field(default=JobMeta(), validate_default=True)
    spec: JobSpec = Field(default=JobSpec(), validate_default=True)
    status: JobStatus = Field(default=JobStatus(), validate_default=True)
    
    def get_namespace(self):
        return self.metadata.namespace


class JobList(ObjectList):
    objects: List[Job] = Field(default=[])

if __name__ == '__main__':
    print(JobList())
