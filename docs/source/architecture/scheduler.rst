
Scheduler Usage, Configuration, and Extension
================================================

The scheduler is responsible for scheduling jobs. It automatically determines the spread of jobs across clusters. This controller is
resource-aware and can be easily customized with different scheduling plugins.

Usage
-----
Each job submission manifest in SkyShift can include both preference and restriction (filters) stanzas for the scheduler to evaluate during
cluster placement.  Both criteria can be used in a job request and is not mutually exclusive.

**Preferences Summary**
A job submission can optionally include multiple cluster placement preferences and associated weights in the job preference stanza.  During
job placement the scheduler checks each cluster defined in the SkyShift system to determine if the expressed preference criteria of the jobs is
satisfied. Details of the criteria expression are describe below.  If the criteria is satisfied a preference weight is retreived from the
stanza as a local weighted preference.  If a cluster satisfies multiple preferences, the highest weighted preference is selected as the
final local weighted preference.  If no matching preference criteria is found for the cluster it is assigned the lowest possible
weight (DEFAULT_MIN_WEIGHT).  
    
**Filters Summary**
A job submission can optionally include multiple cluster placement restrictions expressed as filters.  During
job placement the scheduler checks each cluster defined in the SkyShift system to determine if the expressed filter criteria of the job is
satisfied.  Details of the criteria expression are describe below.  If the criteria is satisfied the cluster is removed from the
available cluster placement list eliminating the ability to place the job on the filtered cluster.

**Placement Stanza**
The job submission includes an optional placement stanza as part of the job specification to enable expressions for both cluster placement 
preferences and restrictions.  Below is a JSON snippit of the placement stanza.

   "spec": {
        "placement": {
            "filters": [
                {
                    "name": "filter-criteria-1",
                    # Sub-stanza match_labels or match_expressions
                    # for filter-criteria-1 defined here
                }, {
                    "name": "filter-criteria-2",
                    # Sub-stanza match_labels or match_expressions
                    # for filter-criteria-2 defined here
                },
            ],
            "preferences": [
                {
                    "name": "pref-criteria-1",
                    # Sub-stanza match_labels or match_expressions
                    # for pref-criteria-1 defined here
                    "weight": 100
                },
                {
                    "name": "pref-criteria-2",
                    # Sub-stanza match_labels or match_expressions
                    # for pref-criteria-2 defined here
                    "weight":
                    50
                },
                {
                    "name": "pref-criteria-3",
                    # Sub-stanza match_labels or match_expressions
                    # for pref-criteria-3 defined here
                    "weight": 25
                },
            ],
        },
    }

In the example JSON snippit above there are 2 filters and 3 preferences defined as part of the job specification.  Within the filter and
preference sub-stanzas, each named criteria is treated as an OR operation of all criteria operations within each sub-stanza.  
Continuing with the JSON snippit above there are 2 filter expressions filter-criteria-1 and filter-criteria-2, 
if a cluster satisfies either named criteria the job would be restricted from being placed on the 
cluster.  For the preferences sub-stanza, the criterias between named preference definitions are also treated as OR operations.  
Note: within each named criteria there are two options to define an expression for evaluation, match-labels or
match_expressions.  In the JSON snippit these definitions are are summarized as a comment and are described in more detail below.  

**Criteria Expressions**
SkyShift enables the ability to labeled clusters with key-value pairs to identify meaningfull attributes.  These labels can be used to
enable advanced scheduling features.  For example if there are 3 clusters (cluster-1, cluster-2, cluster-3) registered in SkyShift and each
cluster has an intended scope for running specific types of workloads such as development, staging, or production workloads, the respective
clusters can be labeled with a scoped attributes using a key-value pair, purpose=development for cluster-1, purpose=staging for cluster-2,
and purpose=production for cluster-3.  Cluster labeling is introduced here to provide prerequisits for enabling advanced scheduling
features for jobs.  More details on labeling clusters is described in the Configuration section below.

There are two options to define an expression for evaluation within each named criteria, the match_labels sub-stanza which can be
used to define an explicit list of cluster labels that must be an exact match in order to meet the criteria, and the 
match-expressions sub-stanza which can be used to define a more expressive critera for cluster label matching.

__Sub-stanze match_labels__
The match_labels sub-stanza can be used to express an explicit list of key-value label pairs for a named criteria.  When the scheduler is
evaluating a job placement the labels of a cluster are matched against all the labels listed within the job's match_labels 
sub-stanza of a filter or preference.  If a cluster's labels match all listed labels within the job's match_labels sub-stanza the
cluster is considered to meet the named criteria.  This evaluation is an AND operation thus if the cluster does not match all of
the listed labels in the match_labels sub-stanza the cluster is not considered to have met the named criteria.

Continuing with the previous JSON snippit example, below is an expansion of the JSON snippit for the first named criteria,
'filter-criteria-1', replacing the comment section: '# Sub-stanza match_labels or match_expression...' with a match_labels 
definition.  

                {
                    "name": "filter-criteria-1",
                    "match_labels": {
                        "purpose": "dev"
                    },
                }, 

In this example, the job containing the placement filter criteria above will be scheduled to run in a cluster annotated with 
the label purpose=dev.  If there are no clusters annotated with the label the job will queue until a cluster annotated with the
label is registered in the SkyShift system.  In otherwords, the intent is to restrict this job to only run on any one 
of the development clusters registered within SkyShift (there can be more than 1).

__Sub-stanze match_expressions_
The match_expressions sub-stanza is a more expressive way to define more complex definitions of label matching.  Expression
label matching is evaluated using the expression opperator.  There are two operators supported in SkyShift, 'In' and 'NotIn'.
For the 'In' operator, a cluster must have the defined key label and at least one of the associated key label 
values (OR operation) for the scheduler to consider the cluster a candidate for placing the job.  
For the 'NotIn' operator, a cluster must not be annotated with any of the defined key-value pair combinations.  Continuing with
the previous JSON snippit example, below is an expansion of the JSON snippit for the second named criteria,
'filter-criteria-2', replacing the comment section: '# Sub-stanza match_labels or match_expression...' with a match_labels 
definition.

                {
                    "name": "filter-criteria-2",
                    "match_expressions": {
                        'key': 'location',
                        'operator': 'In',
                        'values': ['eu', 'us'] 
                    },
                },

In this example, the job containing the placement filter criteria above will be scheduled to run in a cluster annotated with 
the label location=eu or location=us.  If there are no clusters annotated with either label the job will queue until a cluster
annotated with either label is registered in the SkyShift system.  In otherwords, the intent is to restrict this job to run only on clusters
in the EU or in the US.

**Putting it All Together**
The placement stanza is a optional feature that can be used to guide the SkyShift scheduler to restrict or prefer the 
placement of a job.  Details on configuring restrictions (filters) and preferences within the placement stanza are described 
above.  Below is a JSON example of a job definition, named 'my-job' with placement restrictions and preferences.

{
    "kind": "Job",
    "metadata": {
        "name": "my-job"
    },
    "spec": {
        "replicas": "1",
        "image": "ubuntu:latest",
        "resources": {
            "cpus": "1",
            "memory": "128"
        },
        "run": "echo hello_sky; sleep 300",
        "placement": {
            "filters": [{
                "name":
                "filter-1",
                "match_labels": {
                    "purpose": "dev"
                },
                "match_expressions": [{
                    "key": "location",
                    "operator": "NotIn",
                    "values": ["eu"]
                }]
            }, {
                "name":
                "filter-2",
                "match_labels": {
                    "purpose": "staging"
                },
                "match_expressions": [{
                    "key": "location",
                    "operator": "NotIn",
                    "values": ["eu", "ap"]
                }]
            }],
            "preferences": [
                {
                    "name": "pref-1",
                    "match_labels": {
                        "sky-cluster-name": "mycluster-dev-1"
                    },
                    "weight": 100
                },
                {
                    "name":
                    "pref-2",
                    "match_labels": {
                        "purpose": "dev"
                    },
                    "match_expressions": [{
                        "key": "location",
                        "operator": "In",
                        "values": ["na"]
                    }],
                    "weight":
                    50
                },
                {
                    "name": "pref-3",
                    "match_labels": {
                        "purpose": "dev"
                    },
                    "weight": 25
                },
            ]
        }
    }
}

In the JSON example above, when the SkyShift scheduler considers placing 'my-job', it will include any register clusters
as potential placement candidates that are labeled as
development clusters that are not located in the EU.  The scheduler will also include any register clusters that are labeled as
staging clusters that are not located in the EU or AP.  With this superset of restricted clusters the scheduler will then apply a weighted
order of cluster candidates for placement consideration.  The order is defined in the preferences definition and ordered based on defined
weights within each preference.

The scheduling order will first prefer to place the job on a cluster named mycluster-dev-1.  If the job
can not be placed on the named cluster (for example insufficient memory availability) the scheduler will attempt to place the job on a 
development cluster that is located in NA.  A third scheduling attempt if the job can not be placed in any clusters that meet the first two 
preferences is to place the job on any development cluster within the restricted superset of clusters (defined by the filters) regardless
of the location, e.g. a cluster in the US.  Finally if the job can not be placed on any of the prefered clusters, the scheduler will
attempt to place the job within any of the restricted superset of clusters that do not have a preference order. For example,
the job could be placed on a cluster that is labeled as a staging cluster in the US.

Configuration
-------------

**Administration**
In order to utilize the advanced scheduling policies, clusters registered to SkyShift need to be annotated with appropriate
labels.  This process is typically done by a SkyShift administrator.

**Annotating Cluster Labels**
If a cluster is already registered to SkyShift without clusters the administor will first need to remove the registration from
SkyShift.  This can be done using the SkyShift CLI delete subcommand. For example, below is a sample CLI command to remove
a registered Kubernetes cluster named 'cluster-1' from SkyShift:

    sky delete cluster cluster-1

Once the cluster is deleted, it can be re-registered with the SkyShift CLI create subcommand.  For example, to re-registered
the Kubernetes cluster, cluster-1, with two labels, sky-cluster-name=mycluster-dev-1 and purpose=dev the following CLI
command can be issued:

    sky create cluster cluster-1 --manager k8s --labels sky-cluster-name mycluster-dev-1 --labels purpose dev

Further details of the SkyShift CLI can get foudn in the SkyShift CLI documentation.

Scheduler Extensions
--------------------

This controller does not schedule tasks/pods, but instead schedules at a higher level of abstraction - jobs (groups of 
tasks/pods). This enables the scheduler to satisfy gang/coscheduling, colocation, and governance requirements.  The
SkyShift scheduler logic can be modified via the scheduler plugin interface.

**Creating a Custom Scheduler Plugin**
In order to customize the SkyShift scheduler a new plugin can be defined that will need to implement 3
methods defined by the base plugin interface (base_plugin.py).  Below is a description of the 3 methods.

    def filter()
        """Filters the clusters based on the job's defined requirements."""

    def score()
        """Scores the clusters based on the job's scoring requirements.

        This plugin returns a score between 0 and 100. The score is used to rank
        clusters. A score of 0 means the cluster is the least preferred node, and a
        score of 100 means the node is the most preferred cluster.
        """

    def spread()
        """Computes the spread of a job's tasks across clusters.

        Returns the allocated # of tasks that can be scheduled on each cluster.
        """

**Registering a Custom Scheduler Plugin**

Once a custom scheduler plugin is defined, it must be loaded by the SkyShift Scheduler.  This is done
by simply adding the custom plugin into the SkyShift Scheduler Controller (scheduler_controller.py).  Once added, the
SkyShift Scheduler Controller will load the new custom plugin at runtime.
