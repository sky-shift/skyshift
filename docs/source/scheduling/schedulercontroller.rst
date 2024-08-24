====================================
SchedulerController Class
====================================

.. module:: skyshift.scheduler
   :synopsis: The Scheduler Controller manages the high-level scheduling of jobs across multiple clusters.

.. autoclass:: skyshift.scheduler.SchedulerController
   :members:
   :undoc-members:
   :show-inheritance:

Overview
========

The :class:`SchedulerController` is a high-level controller responsible for determining which cluster,
or set of clusters, a job should be placed on within skyshift. This controller operates at the job
level, scheduling entire groups of tasks or pods as jobs, rather than individual tasks or pods. It
enables the fulfillment of advanced scheduling requirements such as gang scheduling, colocation,
and governance, which are not possible with the default Kubernetes scheduler without Custom Resource
Definitions (CRDs) or custom controllers.

The controller continuously monitors cluster and job states, processes events related to them, and
uses various plugins to make scheduling decisions. It relies on flexible plugins to allow for filtering,
scoring, and spreading of jobs across clusters.

Key Responsibilities
=====================

- **Workload Queue Management:**
  Maintains a First-In-First-Out (FIFO) queue of jobs that need scheduling. Jobs are added to this
queue either when they are newly created or when they need to be rescheduled due to failures.

- **Event Processing:**
  Utilizes `Informer` objects to listen for changes in cluster and job states. These changes trigger
scheduling actions, such as adding a job to the workload queue or updating cluster information.

- **Plugin Integration:**
  Applies a series of filter, score, and spread plugins to determine the most suitable cluster(s)
for each job. Plugins are dynamically loaded, allowing for customizable scheduling logic.

- **Cluster and Job Monitoring:**
  Continuously monitors the state of clusters and jobs, ensuring that jobs are placed on clusters
that meet their scheduling criteria. The controller reacts to changes in allocatable resources and
job statuses by re-evaluating job placements.

