from enum import Enum
from typing import List


class JobStatus(Enum):
    INIT = 'INIT'
    # When job has been binded to a node.
    SCHEDULED = 'SCHEDULED'
    # When job has NOT been binded to a node.
    PENDING = 'PENDING'
    # Includes both setup (such as containercreate/pull) and running.
    RUNNING = 'RUNNING'
    # If job has completed.
    COMPLETED = 'COMPLETED'
    # If job has failed execution or violated a FailoverPolicy.
    FAILED = 'FAILED'
    DELETING = 'DELETING'


class JobCreateException(Exception):
    "Raised when the job config is invalid."
    pass


class Job(object):

    def __init__(self,
                 name: str,
                 labels: dict = {},
                 image: str = 'gcr.io/sky-burst/skyburst:latest',
                 resources: dict = {'cpu': 1},
                 run: str = 'echo hello'):
        self.name = name
        self.labels = labels
        self.image = image
        self.resources = resources
        self.run = run
        self.labels['manager'] = 'sky_manager'
        self.metadata = {
            'name': self.name,
            'labels': self.labels,
        }
        self.cluster = None
        self.status = JobStatus.INIT.value
        self.spec = {
            'image': self.image,
            'resources': self.resources,
            'run': self.run,
            'status': self.status,
            'cluster': self.cluster,
        }
        self.cluster_history = []

    @staticmethod
    def from_dict(config: dict):
        assert config['kind'] == 'Job', "Not a Job object: {}".format(config)
        meta = config.pop('metadata', None)
        if meta is None:
            raise JobCreateException('Cluster metadata is missing.')

        try:
            job_name = meta['name']
            labels = meta.pop('labels', {})
            job_obj = Job(name=job_name, labels=labels)
        except KeyError as e:
            raise JobCreateException(f'Job metadata is malformed: {e}.')

        spec = config.pop('spec')
        if spec is not None:
            job_obj.set_spec(spec)

        return job_obj

    def set_spec(self, spec: dict):
        self.image = spec.pop('image', self.image)
        self.resources = spec.pop('resources', self.resources)
        self.run = spec.pop('run', self.run)
        self.status = spec.pop('status', self.status)
        assigned_cluster = spec.pop('cluster', self.cluster)
        self.spec = {
            'image': self.image,
            'resources': self.resources,
            'run': self.run,
            'status': self.status,
            'cluster': assigned_cluster,
        }
        return self.spec

    def update_status(self, status: str):
        self.status = status
        self.spec['status'] = self.status

    def update_cluster(self, cluster: str):
        self.spec['cluster'] = cluster
        self.cluster = cluster

    def __iter__(self):
        yield from {
            'kind': 'Job',
            'metadata': self.metadata,
            'spec': self.spec,
        }.items()


class JobList(object):

    def __init__(self, jobs=List[Job]):
        self.items = jobs

    @staticmethod
    def from_dict(specs: dict):
        assert specs['kind'] == 'JobList', "Not a JobList object: {}".format(
            specs)
        job_list = []
        for job_dict in specs['items']:
            job_list.append(Job.from_dict(job_dict))
        return JobList(job_list)

    def __iter__(self):
        yield from {
            "kind": "JobList",
            'items': [dict(j) for j in self.items]
        }.items()