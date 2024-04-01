from kubernetes import config
from skyflow.utils.base_exceptions import ManagerException

class K8ConnectionError(config.config_exception.ConfigException):
    """Raised when there is an error connecting to the Kubernetes cluster."""
    def __init__(self, msg: str):
        super().__init__(msg)

class UnknownPodStatusError(ManagerException):
    """Raised when the status of a pod is unknown."""
    def __init__(self, msg: str):
        super().__init__(msg)