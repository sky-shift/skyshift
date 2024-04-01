from skyflow.utils.base_exceptions import ObjectException

#### Below are major exceptions for the templates. ####
class ClusterTemplateException(ObjectException):
    """Raised when the cluster template is invalid."""
    pass
        

class EndpointTemplateException(ObjectException):
    """Raised when the endpoint template is invalid."""
    pass
        
        
class WatchEventTemplateException(ObjectException):
    """Raised when the watch event is invalid."""
    pass
        
    
class FilterPolicyTemplateException(ObjectException):
    """Raised when the filter template is invalid."""
    pass
        
        
class JobTemplateException(ObjectException):
    """Raised when the job template is invalid."""
    pass
        

class LinkTemplateException(ObjectException):
    """Raised when the link template is invalid."""
    pass
        

class NamespaceTemplateException(ObjectException):
    """Raised when the namespace template is invalid."""
    pass
        

class RBACTemplateException(ObjectException):
    """Raised when the RBAC template is invalid."""
    pass
        

class ServiceTemplateException(ObjectException):
    """Raised when the service template is invalid."""
    pass        


#### Below are sub-exceptions of the major exceptions above. ####
class RuleException(RBACTemplateException):
    """Raised when the rule is invalid."""
    pass
        

class ServiceSpecException(ServiceTemplateException):
    """Raised when the service spec is invalid."""
    pass
        
        
class ObjectMetaException(ObjectException):
    """Raised when the object metadata is invalid."""
    pass


class NamespacedObjectMetaException(ObjectException):
    """Raised when the namespaced object metadata is invalid."""
    pass
        

class NamespaceStatusException(NamespaceTemplateException):
    """Raised when the namespace status is invalid."""
    pass


class LinkStatusException(LinkTemplateException):
    """Raised when the link status is invalid."""
    pass


class LinkSpecException(LinkTemplateException):
    """Raised when the link spec is invalid."""
    pass

class JobStatusException(JobTemplateException):
    """Raised when the job status is invalid."""
    pass


class JobSpecException(JobTemplateException):
    """Raised when the job spec is invalid."""
    pass


class FilterPolicyStatusException(FilterPolicyTemplateException):
    """Raised when the filter status is invalid."""
    pass


class FilterPolicySpecException(FilterPolicyTemplateException):
    """Raised when the filter spec is invalid."""
    pass


class ClusterFilterException(ClusterTemplateException):
    """Raised when the cluster filter is invalid."""
    pass


class EndpointObjectException(EndpointTemplateException):
    """Raised when the endpoint object is invalid."""
    pass


class EndpointSpecException(EndpointTemplateException):
    """Raised when the endpoint spec is invalid."""
    pass


class ClusterStatusException(ClusterTemplateException):
    """Raised when the cluster status is invalid."""
    pass


class ClusterSpecException(ClusterTemplateException):
    """Raised when the cluster spec is invalid."""
    pass