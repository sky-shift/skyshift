from collections import Counter
import datetime
import enum
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
    """Represents the aggregate status of a job."""
    # When job is first created.
    INIT = 'INIT'
    # When job is currently running.
    ACTIVE = 'ACTIVE'
    # When job is complete.
    COMPLETE = 'COMPLETE'
    # When a job has failed.
    FAILED = 'FAILED'

    def __eq__(self, other):
        if isinstance(other, str):
            return self.value == other
        return super().__eq__(other)

class TaskStatusEnum(enum.Enum):
    """A job consists of many tasks. This enum represents the status of a task."""
    # When a task is first created.
    INIT = 'INIT'
    # When a task is pending (not yet scheduled to a cluster).
    PENDING = 'PENDING'
    # When a task is running.
    RUNNING = 'RUNNING'
    # When a task has completed.
    COMPLETED = 'COMPLETED'
    # When a task has failed execution on the cluster.
    FAILED = 'FAILED'
    # When a task has been evicted from the cluster (either by cluster manager or Flowcontroller).
    EVICTED = 'EVICTED'
    # When a task is in a deletion phase.
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
    # Maps clusters to status of replicas.
    replica_status: Dict[str, Dict[str, int]] = Field(default={}, validate_default=True)
    # Job-IDs for each set of replicas per cluster.
    job_ids: Dict[str, str] = Field(default={}, validate_default=True)

    @field_validator('conditions')
    @classmethod
    def verify_conditions(cls, conditions: List[Dict[str, str]]):
        if not conditions:
            time_str = datetime.datetime.utcnow().isoformat()
            conditions = [{
                'type': JobStatusEnum.INIT.value,
                'transition_time': datetime.datetime.utcnow().isoformat(),
                'update_time': time_str,
            }]
        if len(conditions) == 0:
            raise JobException('Job status\'s condition field is empty.')
        for condition in conditions:
            if 'type' not in condition:
                raise JobException(
                    'Job status\'s condition field is missing status.')
        return conditions
    
    def update_replica_status(self, replica_status: Dict[str, Dict[str, int]]):
        self.replica_status = replica_status

    def update_status(self, status: str):
        if status is None or status not in JobStatusEnum.__members__:
            raise JobException(f'Invalid job status: {status}.')
        # Check most recent status of the cluster.
        previous_status = self.conditions[-1]
        if previous_status['type'] != status:
            time_str = datetime.datetime.utcnow().isoformat()
            self.conditions.append({
                'type': status,
                'transition_time': time_str,
                'update_time': time_str,
            })
        else:
            previous_status['update_time'] = datetime.datetime.utcnow().isoformat()


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
