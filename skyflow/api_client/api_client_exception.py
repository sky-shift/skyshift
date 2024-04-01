from skyflow.utils.base_exceptions import APIException

# This file defines all the expcetions that can be raised by the API client.
# They inherit from the base APIException.

class JobAPIException(APIException):
    """Raised when there is an issue with the Job API."""
    pass
    
    
class ClusterAPIException(APIException):
    """Raised when there is an issue with the Cluster API."""
    pass
        
        
class TokenNotFoundException(APIException):
    """Raised when the user is not found in the config file."""
    pass
        
        
class EndpointAPIException(APIException):
    """Raised when there is an issue with the Endpoint API."""
    pass
        
        
class FilterPolicyAPIException(APIException):
    """Raised when there is an issue with the FilterPolicy API."""
    pass
        
        
class LinkAPIException(APIException):
    """Raised when there is an issue with the Link API."""
    pass
        
        
class NamespaceAPIException(APIException):
    """Raised when there is an issue with the Namespace API."""
    pass
      
class NamespaceObjectAPIException(APIException):
    """Raised when there is an issue with the NamespaceObject API."""
    pass


class APIResponseException(APIException):
    """Raised when there is an issue with the API response."""
    pass
        

class NoNamespaceObjectAPIException(APIException):
    """Raised when there is an issue with the NoNamespaceObject API."""
    pass
    
        
class RuleAPIException(APIException):
    """Raised when there is an issue with the Rule API."""
    pass
        

class ServiceAPIException(APIException):
    """Raised when there is an issue with the Service API."""
    pass