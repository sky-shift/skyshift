from enum import Enum
from typing import List


class ClusterStatus(Enum):
    # Setting up cluster.
    INIT = "INIT"
    # Cluster is ready to accept jobs.
    READY = "READY"
    # Cluster has failed heartbeat.
    FAILED = "FAILED"
    # Deleting cluster (happens during error).
    DELETING = "DELETING"
    # Cluster is in error state.
    ERROR = "ERROR"


class ClusterCreateException(Exception):
    "Raised when the cluster dict is invalid."
    pass


class Cluster(object):

    def __init__(self, name: str, manager_type: str):
        self.name = name
        self.manager_type = manager_type
        self.metadata = {'name': name, 'manager_type': manager_type}
        # Anything in spec is determined by the manager.
        self.status = "INIT"
        self.resources = None
        self.allocatable_resources = None
        self.spec = {
            'status': self.status,
            'resources': self.resources,
            'allocatable_resources': self.allocatable_resources
        }

    @staticmethod
    def from_dict(config: dict):
        assert config['kind'] == 'Cluster', "Not a Cluster object: {}".format(
            config)
        meta = config.pop('metadata', None)
        if meta is None:
            raise ClusterCreateException('Cluster metadata is missing.')

        try:
            cluster_obj = Cluster(meta['name'], meta['manager_type'])
        except KeyError as e:
            raise ClusterCreateException(
                f'Cluster metadata is malformed: {e}.')

        spec = config.pop('spec', None)
        if spec:
            cluster_obj.set_spec(spec)
        return cluster_obj

    def set_spec(self, spec: dict):
        self.status = spec.pop('status', None)
        self.resources = spec.pop('resources', None)
        self.allocatable_resources = spec.pop('allocatable_resources', None)
        self.spec = {
            'status': self.status,
            'resources': self.resources,
            'allocatable_resources': self.allocatable_resources,
        }
        return self.spec

    def __iter__(self):
        yield from {
            'kind': 'Cluster',
            'metadata': self.metadata,
            'spec': self.spec,
        }.items()

    def __repr__(self):
        return str(self.to_dict())


class ClusterList(object):

    def __init__(self, clusters: List[Cluster] = []):
        self.items = clusters

    @staticmethod
    def from_dict(specs: dict):
        assert specs[
            'kind'] == 'ClusterList', "Not a ClusterList object: {}".format(
                specs)
        cluster_list = []
        for cluster_dict in specs['items']:
            cluster_list.append(Cluster.from_dict(cluster_dict))
        return ClusterList(cluster_list)

    def __iter__(self):
        yield from {
            "kind": "ClusterList",
            'items': [dict(c) for c in self.items]
        }.items()