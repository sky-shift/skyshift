
.. _examples:

BookInfo Application Example
==================

This example demonstrates how an application like `Istio BookInfo <https://istio.io/latest/docs/examples/bookinfo/>`_ can be deployed using Skyshift.
This test uses two k8s clusters:

* Cluster1 : A Product-Page microservice (application frontend) and details microservice run on the first cluster, which is used as frontend.
* Cluster2 : A Reviews-V2 (display rating with black stars) and Rating microservices run on the second cluster, used as backend.

1) Start Skyshift using the commands listed in :ref:`Setup Guide <setup>`.

2) Add the first cluster to Skyshift.

Optionally, Create and configure KIND cluster.

.. code-block:: shell

    kind create cluster --name=cluster1

Next, enable MetalLB to provision loadbalancer for creating service with external IP, since this will be a frontend cluster.

.. code-block:: shell

    kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.13.10/config/manifests/metallb-native.yaml


Check the status of the MetalLB pods using the following command, and wait until they are in running state.

.. code-block:: shell

    kubectl get pods -n metallb-system

Once the pods are in running state, apply the following configuration.

.. code-block:: shell
        
    sleep 5
    kubectl apply -f - <<EOF
    apiVersion: metallb.io/v1beta1
    kind: IPAddressPool
    metadata:
        name: kind-pool
        namespace: metallb-system
     spec:
        addresses:
            - 172.18.255.1-172.18.255.250  # Choose an IP range that doesn't conflict with your local network
    ---
    apiVersion: metallb.io/v1beta1
    kind: L2Advertisement
    metadata:
        name: kind-advertisement
        namespace: metallb-system
    EOF

Finally, add this cluster to Skyshift with label as frontend.

.. code-block:: shell  

    skyctl create cluster --manager k8 kind-cluster1 --labels type frontend

3) Now, add the second cluster to Skyshift with label as backend.
 
Optionally, Create KIND cluster.

.. code-block:: shell

    kind create cluster --name=cluster2

.. code-block:: shell  

    skyctl create cluster --manager k8 kind-cluster2 --labels type backend

4) Submit the jobs productpage and details microservice to Skyshift.

.. code-block:: shell

    export SKYSHIFT=<Path to cloned Skyshift directory>
    
.. code-block:: shell

    skyctl apply -f $SKYSHIFT/examples/bookinfo-demo/productpage.yaml
    
.. code-block:: shell

    skyctl apply -f $SKYSHIFT/examples/bookinfo-demo/details.yaml
    

Verify if the jobs  are in running state and scheduled in kind-cluster1.

.. code-block:: shell

    $ skyctl get jobs
    ⠙ Fetching jobs
    NAME         CLUSTER        REPLICAS    RESOURCES          NAMESPACE    STATUS    AGE
    details-v1   kind-cluster1  1/1         cpus: 7.0          default      RUNNING   12s
                                            memory: 128.00 MB
    productpage  kind-cluster1  1/1         cpus: 7.0          default      RUNNING   18s
                                            memory: 128.00 MB
    ✔ Fetching jobs completed successfully.

5) Create a service for the jobs.

.. code-block:: shell

    skyctl apply -f $SKYSHIFT/examples/bookinfo-demo/productpage_service.yaml 

.. code-block:: shell

    skyctl apply -f $SKYSHIFT/examples/bookinfo-demo/details_service.yaml 

6) Deploy reviews and ratings microservice in cluster2.

.. code-block:: shell

    skyctl apply -f $SKYSHIFT/examples/bookinfo-demo/ratings.yaml

.. code-block:: shell

    skyctl apply -f $SKYSHIFT/examples/bookinfo-demo/reviews.yaml

.. note::
    Ideally, now the jobs must be running in the clusters similar to below output,
    productpage, and details-v1 are scheduled in kind-cluster1, while ratings-v1, and reviews-v2 are scheduled in kind-cluster2.

.. code-block:: shell

    $ skyctl get jobs
    ⠙ Fetching jobs
    NAME         CLUSTER        REPLICAS    RESOURCES          NAMESPACE    STATUS    AGE
    details-v1   kind-cluster1  1/1         cpus: 7.0          default      RUNNING   14m
                                            memory: 128.00 MB
    productpage  kind-cluster1  1/1         cpus: 7.0          default      RUNNING   15m
                                            memory: 128.00 MB
    ratings-v1   kind-cluster2  1/1         cpus: 7.0          default      RUNNING   47s
                                            memory: 128.00 MB
    reviews-v2   kind-cluster2  1/1         cpus: 7.0          default      RUNNING   15s
                                                memory: 128.00 MB
    ✔ Fetching jobs completed successfully.

7) Create a link between the two clusters.
    
.. code-block:: shell

    skyctl create link -s kind-cluster1 -t kind-cluster2 clink

8) Now, we create reviews service in cluster1, so that it is accessible to productpage.

.. code-block:: shell

    skyctl apply -f $SKYSHIFT/examples/bookinfo-demo/ratings_service.yaml

.. code-block:: shell

    skyctl apply -f $SKYSHIFT/examples/bookinfo-demo/reviews_service.yaml

.. note::
    At this point it uses `clusterlink <https://clusterlink.net>`_ to import the reviews service from cluster2 .

9) Now, we can try to access the productpage frontend application.

.. code-block:: shell

    export FRONTEND_IP=`kubectl get svc productpage --context kind-cluster1 -o jsonpath='{.status.loadBalancer.ingress[0].ip}'`

.. note::
    Open http://$FRONTEND_IP/productpage in browser, and you should be able to view the rating/reviews of the book as shown below.

.. image:: /_static/bookinfo.png
  :width: 100%
  :align: center
  :alt: SkyShift Architecture Diagram
  :class: no-scaled-link, only-dark


10) Finally, Cleanup.

    .. code-block:: shell

        ./cleanup.sh
    