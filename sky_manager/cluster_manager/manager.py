from sky_manager.templates.cluster_template import Cluster


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

    @property
    def cluster_state(self):
        """ Gets the cluster state. """
        cluster_manager_obj = Cluster(self.name, manager_type='k8')
        cluster_manager_obj.set_spec({
            'status':
            'READY',
            'resources':
            self.cluster_resources,
            'allocatable_resources':
            self.allocatable_resources
        })
        return dict(cluster_manager_obj)

    def submit_job(self, job):
        raise NotImplementedError

    def get_job_status(self, job_name):
        raise NotImplementedError

    @staticmethod
    def convert_yaml(job):
        raise NotImplementedError
