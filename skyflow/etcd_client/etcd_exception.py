from skyflow.utils.base_exceptions import ETCDException
from typing import Optional

class ConflictError(ETCDException):
    """Exception raised when there is a conflict in the ETCD store."""

    def __init__(self, msg: str, resource_version: Optional[int] = None):
        self.msg = msg
        self.resource_version = resource_version
        super().__init__(self.msg)


class KeyNotFoundError(ETCDException):
    """Exception raised when a requested key does not exist."""

    def __init__(self,
                 key: str,
                 msg: str = "The requested key does not exist."):
        self.key = key
        self.msg = msg
        super().__init__(self.msg)
        