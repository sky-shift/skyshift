
# BookInfo  Example

This example demonstrates how an application like [Istio BookInfo](https://istio.io/latest/docs/examples/bookinfo/) can be deployed using Skyshift
This test uses two k8s clusters:

* Cluster1 : A Product-Page microservice (application frontend) and details microservice run on the first cluster, which is used as frontend.
* Cluster2 : A Reviews-V2 (display rating with black stars) and Rating microservices run on the second cluster, used as backend.

1) Start Skyshift using the commands listed in [README.md](../../README.md).

2) Add the first cluster to Skyshift

    Optionally, Create and configure KIND cluster
    ```
    kind create cluster --name=cluster1
    ```
    Next, enable MetalLB to provision loadbalancer for creating service with external IP, since this will be a frontend cluster

    ```
    kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.13.10/config/manifests/metallb-native.yaml
    ```

    Check the status of the MetalLB pods using the following command, and wait until they are in running state

    ```
    kubectl get pods -n metallb-system
    ```
    Once the pods are in running state, apply the following configuration.

    ```
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
    ```

    Finally, add this cluster to Skyshift with label as frontend.

    ```  
    skyctl create cluster --manager k8 kind-cluster1 --labels type frontend
    ```
3) Now, add the second cluster to Skyshift with label as backend
    Optionally, Create KIND cluster
    ```
    kind create cluster --name=cluster2
    ```

    ```     
    skyctl create cluster --manager k8 kind-cluster2 --labels type backend
    ```
4) Submit the jobs productpage and details microservice to Skyshift

    ```
    export SKYSHIFT=<Path to cloned Skyshift directory>
    ```

    ```
    skyctl apply -f $SKYSHIFT/examples/bookinfo-demo/productpage.yaml
    ```
    ```
    skyctl apply -f $SKYSHIFT/examples/bookinfo-demo/details.yaml
    ```

    Verify if the jobs  are in running state and scheduled in kind-cluster1
    ```
    $ skyctl get jobs
    ⠙ Fetching jobs
    NAME         CLUSTER        REPLICAS    RESOURCES          NAMESPACE    STATUS    AGE
    details-v1   kind-cluster1  1/1         cpus: 7.0          default      RUNNING   12s
                                            memory: 128.00 MB
    productpage  kind-cluster1  1/1         cpus: 7.0          default      RUNNING   18s
                                            memory: 128.00 MB
    ✔ Fetching jobs completed successfully.
    ```
5) Create a service for the jobs
    ```
    skyctl apply -f $SKYSHIFT/examples/bookinfo-demo/productpage_service.yaml 

    ```
    ```
    skyctl apply -f $SKYSHIFT/examples/bookinfo-demo/details_service.yaml 
    ```

6) Deploy reviews and ratings microservice in cluster2

    ```
    skyctl apply -f $SKYSHIFT/examples/bookinfo-demo/ratings.yaml
    ```
    ```
    skyctl apply -f $SKYSHIFT/examples/bookinfo-demo/reviews.yaml
    ```
    Ideally, now the jobs must be running in the clusters similar to below output,
    productpage, and details-v1 are scheduled in kind-cluster1, while ratings-v1, and reviews-v2 are scheduled in kind-cluster2

    ```
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
    ```
7) Create a link between the two clusters
    ```
    skyctl create link -s kind-cluster1 -t kind-cluster2 clink
    ```

8) Now, we create reviews service in cluster1, so that it is accessible to productpage.

    ```
    skyctl apply -f $SKYSHIFT/examples/bookinfo-demo/ratings_service.yaml
    ```

    ```
    skyctl apply -f $SKYSHIFT/examples/bookinfo-demo/reviews_service.yaml
    ```

     At this point it uses [clusterlink](https://clusterlink.net) to import the reviews service from cluster2 

9) Now, we can try to access the productpage frontend application using

    ```
    export FRONTEND_IP=`kubectl get svc productpage --context kind-cluster1 -o jsonpath='{.status.loadBalancer.ingress[0].ip}'`
    ```
    open http://$FRONTEND_IP/productpage in browser, and you should be able to view the rating/reviews of the book as shown below.

![Bookinfo demo](../../docs/source/_static/bookinfo.png)
10) Finally, Cleanup

    ```
    ./cleanup.sh
    ```