"""
Init module for Skyflow object templates.
"""
from skyflow.templates.cluster_template import (Cluster,
                                                ClusterList, ClusterStatus,
                                                ClusterStatusEnum)
from skyflow.templates.endpoints_template import (EndpointObject, Endpoints,
                                                  EndpointsList, EndpointsMeta,
                                                  EndpointsSpec,
                                                  EndpointsStatus)
from skyflow.templates.event_template import WatchEvent, WatchEventEnum
from skyflow.templates.filter_policy import (FilterPolicy,
                                             FilterPolicyList)
from skyflow.templates.job_template import (Job, JobList,
                                            JobStatusEnum, RestartPolicyEnum,
                                            TaskStatusEnum)
from skyflow.templates.link_template import (Link, LinkList,
                                             LinkStatus, LinkStatusEnum)
from skyflow.templates.namespace_template import (Namespace,
                                                  NamespaceList, NamespaceMeta)
from skyflow.templates.object_template import (Object,
                                               ObjectList, ObjectMeta,
                                               ObjectSpec, ObjectStatus)
from skyflow.templates.rbac_template import Role, RoleList
from skyflow.templates.resource_template import AcceleratorEnum, ResourceEnum
from skyflow.templates.service_template import (Service, 
                                                ServiceList, ServiceMeta)
from skyflow.templates.user_template import User

__all__ = [
    "AcceleratorEnum",
    "Cluster",
    "ClusterList",
    "ClusterStatus",
    "ClusterStatusEnum",
    "Endpoints",
    "EndpointsList",
    "EndpointsMeta",
    "EndpointsSpec",
    "EndpointsStatus",
    "EndpointObject",
    "FilterPolicy",
    "FilterPolicyList",
    "Job",
    "JobList",
    "JobStatusEnum",
    "Link",
    "LinkList",
    "LinkStatus",
    "LinkStatusEnum",
    "Namespace",
    "NamespaceMeta",
    "NamespaceList",
    "ResourceEnum",
    "RestartPolicyEnum",
    "Role",
    "RoleList",
    "Service",
    "ServiceList",
    "ServiceMeta",
    "Object",
    "ObjectList",
    "ObjectMeta",
    "ObjectSpec",
    "ObjectStatus",
    "TaskStatusEnum",
    "WatchEvent",
    "WatchEventEnum",
    "User",
]
