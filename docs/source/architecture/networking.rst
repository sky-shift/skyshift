Networking across clusters
===========================
SkyShift builds a network mesh between clusters to allow jobs/services to communicate between themselves. 
This is applicable in two scenarios:

1) A service's replicas are scheduled on multiple clusters due to resource constraints, 
while the frontend is serving and balancing the load from one of the cluster.

2) Jobs that are deployed across clusters have a need to communicate to fulfil a larger application goal.

This network mesh is constructed on demand using `Clusterlink <https://clusterlink.net>`_. 
Clusterlink simplifies the connection between application services that are located in different domains, networks, and cloud infrastructures.
It deploys a set of unpriviliged gateways serving connections to and from services according to policies defined in the management plane.
ClusterLink gateways represent the remotely deployed services to applications running in a local cluster, acting as L4 proxies. 
On connection establishment, the control plane components in the source and the target ClusterLink gateways validate 
and establish a secure mTLS connection based on specified policies.

How SkyShift sets up ClusterLink
---------------------------------
When Skyshift is launched, it automatically installs the clusterlink binary and sets up the network `fabric <https://clusterlink.net/docs/main/concepts/fabric/>`_ by
invoking clusterlink APIs to create a root certificate, and key pairs for each cluster that is managed by Skyshift.

Skyshift additionally deploys the clusterlink gateways in the cluster and utilizes the management API to do the following :

1) `Create link <https://clusterlink.net/docs/main/concepts/peers/#add-or-remove-peers>`_ or establish peering between two clusterlink gateways.

2) `Exporting a service <https://clusterlink.net/docs/main/concepts/services/>`_ from a cluster.

3) `Importing a service <https://clusterlink.net/docs/main/concepts/services/>`_ from a cluster.

4) `Apply policy <https://clusterlink.net/docs/main/concepts/policies/>`_ on the underlying inter-cluster communication.

Essentially, the above three operations are key to setting up the inter-cluster comunication in SkyShift.

Future Enhancements
-------------------
Currently, SkyShift supports Clusterlink deployment and operation for Kubernetes Cluster. Looking ahead,
SkyShift aims to support inter-cluster communications on workloads deployed on SLURM and Ray clusters as well. 