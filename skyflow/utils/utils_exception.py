from skyflow.utils.base_exceptions import UtilsException

class ObjectLoadingError(UtilsException):
    """Raised when the object dict is invalid."""
    pass

class InvalidClusterNameError(UtilsException):
    """Raised when the cluster name is invalid."""
    pass