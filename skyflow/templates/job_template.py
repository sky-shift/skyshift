"""
Job template for Skyflow.
"""
import enum
import re
from copy import deepcopy
from datetime import datetime, timezone
from typing import Dict, List

from pydantic import Field, field_validator

from skyflow.templates.object_template import (NamespacedObjectMeta, Object,
                                               ObjectList,
                                               ObjectSpec, ObjectStatus)
from skyflow.templates.resource_template import AcceleratorEnum, ResourceEnum
from skyflow.templates.templates_exception import JobTemplateException, JobStatusException, JobSpecException


DEFAULT_IMAGE = "ubuntu:latest"
DEFAULT_JOB_RESOURCES = {
    ResourceEnum.CPU.value: 1,
    ResourceEnum.MEMORY.value: 0,
}
DEFAULT_NAMESPACE = "default"


class JobStatusEnum(enum.Enum):
    """Represents the aggregate status of a job."""

    # When job is first created.
    INIT = "INIT"
    # When job is currently running.
    ACTIVE = "ACTIVE"
    # When job is complete.
    COMPLETE = "COMPLETE"
    # When a job has failed.
    FAILED = "FAILED"

    def __eq__(self, other):
        if isinstance(other, str):
            return self.value == other
        return super().__eq__(other)


class TaskStatusEnum(enum.Enum):
    """A job consists of many tasks. This enum represents the status of a task."""

    # When a task is first created.
    INIT = "INIT"
    # When a task is pending (not yet scheduled to a cluster).
    PENDING = "PENDING"
    # When a task is running.
    RUNNING = "RUNNING"
    # When a task has completed.
    COMPLETED = "COMPLETED"
    # When a task has failed execution on the cluster.
    FAILED = "FAILED"
    # When a task has been evicted from the cluster (either by cluster manager or Flowcontroller).
    EVICTED = "EVICTED"
    # When a task is in a deletion phase.
    DELETED = "DELETED"

    def __eq__(self, other):
        if isinstance(other, str):
            return self.value == other
        return super().__eq__(other)


class ContainerStatusEnum(enum.Enum):
    """A job consists of many containers. This enum represents the status of a container."""
    RUNNING = "RUNNING"
    TERMINATED = "TERMINATED"
    WAITING = "WAITING"
    PULLED = "PULLED"
    UNKNOWN = "UNKNOWN"

    def __eq__(self, other):
        if isinstance(other, str):
            return self.value == other
        return super().__eq__(other)


class RestartPolicyEnum(enum.Enum):
    """Represents the restart policy of a job."""

    # Never restart job (even if it fails).
    NEVER = "Never"
    # Always restart job (even if it succeeds, RC=0).
    ALWAYS = "Always"
    # Only restart job if it fails (RC!=0).
    ON_FAILURE = "OnFailure"

    def __eq__(self, other):
        if isinstance(other, str):
            return self.value == other
        return super().__eq__(other)

    @classmethod
    def has_value(cls, value):
        """
        Checks if the specified value is present among the enum values.
        """
        return any(value == item.value for item in cls)


class JobStatus(ObjectStatus):
    """Status of a job."""
    conditions: List[Dict[str, str]] = Field(default=[], validate_default=True)
    # Maps clusters to status of replicas.
    replica_status: Dict[str, Dict[str, int]] = Field(default={},
                                                      validate_default=True)
    # Job-IDs for each set of replicas per cluster.
    job_ids: Dict[str, str] = Field(default={}, validate_default=True)

    # Task-IDs for each set of replicas per cluster.
    task_status: Dict[str, Dict[str, str]] = Field(default={},
                                                   validate_default=True)

    container_status: Dict[str, Dict[str, str]] = Field(default={},
                                                        validate_default=True)

    @field_validator("conditions")
    @classmethod
    def verify_conditions(cls, conditions: List[Dict[str, str]]):
        """Validates the conditions field of a job."""
        if not conditions:
            time_str = datetime.now(timezone.utc).isoformat()
            conditions = [{
                "type":
                JobStatusEnum.INIT.value,  # pylint: disable=no-member
                "transition_time":
                datetime.now(timezone.utc).isoformat(),
                "update_time":
                time_str,
            }]
        if len(conditions) == 0:
            raise JobStatusException("Job status's condition field is empty.")
        for condition in conditions:
            if "type" not in condition:
                raise JobStatusException(
                    "Job status's condition field is missing status.")
        return conditions

    def update_replica_status(self, replica_status: Dict[str, Dict[str, int]]):
        """Updates the replica status field of a job."""
        self.replica_status = replica_status

    def update_status(self, status: str):
        """Updates the status field of a job."""
        if status is None or status not in JobStatusEnum.__members__:
            raise JobStatusException(f"Invalid job status: {status}.")
        # Check most recent status of the cluster.
        previous_status = self.conditions[-1]
        if previous_status["type"] != status:
            time_str = datetime.now(timezone.utc).isoformat()
            self.conditions.append({
                "type": status,
                "transition_time": time_str,
                "update_time": time_str,
            })
        else:
            previous_status["update_time"] = datetime.now(
                timezone.utc).isoformat()


class JobMeta(NamespacedObjectMeta):
    """Metadata of a job."""


class JobSpec(ObjectSpec):
    """Spec of a job."""
    image: str = Field(default=DEFAULT_IMAGE, validate_default=True)
    resources: Dict[str, float] = Field(default=DEFAULT_JOB_RESOURCES,
                                        validate_default=True)
    run: str = Field(default="", validate_default=True)
    envs: Dict[str, str] = Field(default={}, validate_default=True)
    ports: List[int] = Field(default=[], validate_default=True)
    replicas: int = Field(default=1, validate_default=True)
    restart_policy: str = Field(default=RestartPolicyEnum.ALWAYS.value,
                                validate_default=True)

    @field_validator('image')
    @classmethod
    def validate_image(cls, image):
        """
        Function to check if the image is in the correct format.
        """
        pattern = r'^([a-zA-Z0-9.-]+)?(:[a-zA-Z0-9._-]+)?(/[a-zA-Z0-9._/-]+)?(:[a-zA-Z0-9._-]+|@sha256:[a-fA-F0-9]{64})?$'  # pylint: disable=line-too-long

        if image == "" or not re.match(pattern, image):
            raise ValueError(
                'Invalid image format. Expected format: [repository/]image[:tag] or\
                      [repository/]image[@digest].')
        return image

    @field_validator("ports")
    @classmethod
    def verify_ports(cls, ports: List[int]) -> List[int]:
        """Validates the ports field of a job."""
        for port in ports:
            if port <= 0 or port > 65535:
                raise JobSpecException(f"Invalid port: {port}.")
        return ports

    @field_validator("replicas")
    @classmethod
    def verify_replicas(cls, replicas: int) -> int:
        """Validates the replicas field of a job."""
        if replicas <= 0:
            raise JobSpecException(f"Invalid replicas: {replicas}.")
        return replicas

    @field_validator("restart_policy")
    @classmethod
    def verify_restart_policy(cls, restart_policy: str) -> str:
        """Validates the restart_policy field of a job."""
        if restart_policy is None or restart_policy not in [
                r.value for r in RestartPolicyEnum
        ]:
            raise JobSpecException(f"Invalid restart policy: {restart_policy}.")
        return restart_policy

    @field_validator("resources")
    @classmethod
    def verify_resources(cls, resources: Dict[str, float]):
        """Validates the resources field of a job."""
        resources = {**deepcopy(DEFAULT_JOB_RESOURCES), **resources}
        resource_enums = [member.value for member in ResourceEnum]
        acc_enums = [member.value for member in AcceleratorEnum]
        for resource_type, resource_value in resources.items():
            if resource_type not in resource_enums and resource_type not in acc_enums:
                raise JobSpecException(f"Invalid resource type: {resource_type}.")
            if resource_value < 0:
                raise JobSpecException(
                    f"Invalid resource value for {resource_type}: {resource_value}."
                )

            if resource_type in acc_enums and ResourceEnum.GPU.value in resources:
                raise JobSpecException(
                    f"Cannot specify both GPU and accelerator type {resource_type} simultaneously."
                )

        return resources


class Job(Object):
    """Job object."""
    metadata: JobMeta = Field(default=JobMeta(), validate_default=True)
    spec: JobSpec = Field(default=JobSpec(), validate_default=True)
    status: JobStatus = Field(default=JobStatus(), validate_default=True)

    def get_namespace(self):
        """Returns the namespace of the job."""
        return self.metadata.namespace  # pylint: disable=no-member


class JobList(ObjectList):
    """List of jobs."""
    kind: str = Field(default="JobList")


if __name__ == "__main__":
    print(JobList())
