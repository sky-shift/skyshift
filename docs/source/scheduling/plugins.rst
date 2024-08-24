SchedulerController Plugins
===========================

This doc provides an overview of the plugins used by the SchedulerController
to manage job scheduling across multiple clusters.

BasePlugin
----------

**Overview:**
The **BasePlugin** acts as the  template for all other scheduling plugins
for the SchedulerController. It defines the essential structure for three
primary actions: filtering, scoring, and spreading jobs across clusters.

**Implementation:**
- **Filter Method:** This method should be overridden in derived classes
to implement specific filtering logic based on job and cluster properties.

- **Score Method:** This should also be customized in subclasses to provide
meaningful scoring mechanisms based on the job’s resource requirements
and cluster resources.

- **Spread Method:** This method is used distribute job tasks across
clusters, returns an error by default, and requires an override in
subclasses.

ClusterAffinityPlugin
---------------------

**Overview:**
The **ClusterAffinityPlugin** filters clusters based on specific job
affinity rules.

**Implementation Details:**
- **Filter Logic:** Integrates with `FilterPolicyAPI` to retrieve filter
policies and applies them by checking if the cluster's attributes match
the job's label requirements. It supports include/exclude lists, providing
a mechanism to enforce job affinity rules strictly.

ClusterAffinityPluginV2
-----------------------

**Overview:**
The **ClusterAffinityPluginV2** supports multi-criteria filtering compared
to ClusterAffinityPlugin.

**Implementation Details:**
 This plugin processes job-defined filters to asses cluster compatibility by
checking if clusters have requisite labels matching job specifications, such
as hardware versions or software configurations.

- **Filtering Process:**
  1. **Extract Filter Specifications:** Retrieves detailed filter criteria from
the job's specifications, which dictate the necessary attributes a cluster must possess.
  2. **Evaluate Clusters:** Each cluster is assessed against these criteria using both
label matches and logical conditions to asses the suitability.

DefaultPlugin
-------------

**Overview:**
The **DefaultPlugin** provides default implementations of filtering and scoring methods.

**Implementation Details:**
- **Filter Method:** Checks if a cluster has the necessary resources to accommodate a job,
by comparing the available capacities and job specifications. This ensures that only
eligible clusters are selected for job placement.

- **Score Method:** Calculates scores based on the availability of resources such as CPUs
and GPUs, with additional weighting based on job preferences. This weighted scoring system
helps prioritize clusters based on user preferences.

- **Spread Method:** Implements a strategy to distribute job replicas across clusters based
on their capacity, using a greedy algorithm to maximize resource utilization and balance
load across the available infrastructure.
