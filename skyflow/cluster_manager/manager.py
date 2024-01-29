from skyflow.templates.cluster_template import ClusterStatus, ClusterStatusEnum


class ManagerException(Exception):
    """Raised when the manager is invalid."""
    pass


class Manager(object):
    """
    General manager object.

    Serves as the base class for the compatability layer across cluster
    managers.
    """

    def __init__(self, name: str):
        self.cluster_name = name

    @property
    def cluster_resources(self):
        """
        Fetches total cluster resources.
        """
        raise NotImplementedError

    @property
    def allocatable_resources(self):
        """
        Fetches allocatable cluster resources.
        """
        raise NotImplementedError

    def get_cluster_status(self):
        """ Gets the cluster status. """
        return ClusterStatus(
            status=ClusterStatusEnum.READY.value,
            capacity=self.cluster_resources,
            allocatable_capacity=self.allocatable_resources,
        )

    def get_jobs_status(self):
        """Gets the status for all jobs."""
        return

    def submit_job(self, job):
        raise NotImplementedError

    def get_job_status(self, job_name):
        raise NotImplementedError

    @staticmethod
    def convert_yaml(job):
        raise NotImplementedError
