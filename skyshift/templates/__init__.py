"""
Init module for SkyShift object templates.
"""
from skyshift.templates.cluster_template import (Cluster, ClusterException,
                                                 ClusterList, ClusterStatus,
                                                 ClusterStatusEnum)
from skyshift.templates.endpoints_template import (EndpointObject, Endpoints,
                                                   EndpointsException,
                                                   EndpointsList,
                                                   EndpointsMeta,
                                                   EndpointsSpec,
                                                   EndpointsStatus)
from skyshift.templates.event_template import WatchEvent, WatchEventEnum
from skyshift.templates.filter_policy import (FilterPolicy,
                                              FilterPolicyException,
                                              FilterPolicyList)
from skyshift.templates.job_template import (Job, JobException, JobList,
                                             JobStatusEnum,
                                             LabelSelectorOperatorEnum,
                                             MatchExpression,
                                             RestartPolicyEnum, TaskStatusEnum)
from skyshift.templates.link_template import (Link, LinkException, LinkList,
                                              LinkStatus, LinkStatusEnum)
from skyshift.templates.namespace_template import (Namespace,
                                                   NamespaceException,
                                                   NamespaceList,
                                                   NamespaceMeta)
from skyshift.templates.object_template import (Object, ObjectException,
                                                ObjectList, ObjectMeta,
                                                ObjectSpec, ObjectStatus)
from skyshift.templates.rbac_template import Role, RoleList
from skyshift.templates.resource_template import (AcceleratorEnum, CRIEnum,
                                                  ResourceEnum)
from skyshift.templates.service_template import (Service, ServiceException,
                                                 ServiceList, ServiceMeta)
from skyshift.templates.user_template import User

__all__ = [
    "AcceleratorEnum",
    "CRIEnum",
    "Cluster",
    "ClusterException",
    "ClusterList",
    "ClusterStatus",
    "ClusterStatusEnum",
    "Endpoints",
    "EndpointsException",
    "EndpointsList",
    "EndpointsMeta",
    "EndpointsSpec",
    "EndpointsStatus",
    "EndpointObject",
    "FilterPolicy",
    "FilterPolicyException",
    "FilterPolicyList",
    "Job",
    "JobException",
    "JobList",
    "JobStatusEnum",
    "Link",
    "LinkException",
    "LinkList",
    "LinkStatus",
    "LinkStatusEnum",
    "Namespace",
    "NamespaceException",
    "NamespaceMeta",
    "NamespaceList",
    "ResourceEnum",
    "RestartPolicyEnum",
    "Role",
    "RoleList",
    "Service",
    "ServiceException",
    "ServiceList",
    "ServiceMeta",
    "Object",
    "ObjectException",
    "ObjectList",
    "ObjectMeta",
    "ObjectSpec",
    "ObjectStatus",
    "TaskStatusEnum",
    "WatchEvent",
    "WatchEventEnum",
    "User",
]
