from skyflow.utils.base_exceptions import MockTestException

class NoJsonDataError(MockTestException):
    """Raised when no mock data is available for the request."""
    pass