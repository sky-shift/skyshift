# This file defines the three base exceptions used in the Skyflow project. All detailed exceptions should inherit from these.
class APIException(Exception):
    """The Base Exception for all API Exceptions."""
    def __init__(self, msg, status_code=None):
        self.status_code = status_code
        self.msg = msg
        super().__init__(msg)
        
        
class ObjectException(Exception):
    """Raised when the object dict is invalid."""

    def __init__(self, message="Failed to create object."):
        self.message = message
        super().__init__(self.message)


class ManagerException(Exception):
    """The Base Exception for all Manager Exceptions."""
    def __init__(self, msg):
        self.msg = msg
        super().__init__(msg)
        

class ETCDException(Exception):
    """The Base Exception for all ETCD Exceptions."""
    def __init__(self, msg):
        self.msg = msg
        super().__init__(msg)
        
        
class MockTestException(Exception):
    """The Base Exception for all Mock Test Exceptions."""
    def __init__(self, msg):
        self.msg = msg
        super().__init__(msg)
        

class UtilsException(Exception):
    """The Base Exception for all Utils Exceptions."""
    def __init__(self, msg):
        self.msg = msg
        super().__init__(msg)