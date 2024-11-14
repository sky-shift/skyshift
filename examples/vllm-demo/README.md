
# vLLM Serving Example

This example demonstrates how an application like LLM serving using [vLLM](https://vllm.ai/) can be deployed and scaled using Skyshift
This example uses two k8s clusters with a single node with 1 GPU. We will be deploying two replicas of meta-llama model over vLLM, and Skyshift will 
deploy the replicas across two clusters and load balance the requests between the two replicas.

## Pre-requisite

1) Two K8s clusters:
    - Cluster1 with 1 nvidia GPU
    - Cluster2 with 1 nvidia GPU

    For instance, lets assume the GPU type is nvidia L4
    ```
    $ skyctl get clusters
    ⠙ Fetching clusters
    NAME       MANAGER    LABELS    RESOURCES                  STATUS    AGE
    cluster1   k8                   cpus: 14.29/15.88          READY     49s
                                    memory: 70.09 GB/71.92 GB
                                    disk: 87.05 GB/87.05 GB
                                    L4: 1.0/1.0
    cluster2   k8                   cpus: 14.29/15.88          READY     49s
                                    memory: 70.09 GB/71.92 GB
                                    disk: 87.05 GB/87.05 GB
                                    L4: 1.0/1.0
    ```                              
1) Start Skyshift using the commands listed in [README.md](../../README.md).

2) Add the two clusters to Skyshift

    ```  
    skyctl create cluster --manager k8 cluster1
    ```
    ```     
    skyctl create cluster --manager k8 cluster2
    ```

3) Create a link between the two clusters
    ```
    skyctl create link -s cluster1 -t cluster2 clink
    ```

4) Submit the vllm job with two replicas to Skyshift

    ```
    export SKYSHIFT=<Path to cloned Skyshift directory>
    ```

    Add the HuggingFace Hub token if the model is gated.

    ```
    yq eval '.spec.envs.HUGGING_FACE_HUB_TOKEN = "your_token_value"' -i $SKYSHIFT/examples/vllm-demo/vllm.yaml
    ```

    Submit the job.

    ```
    skyctl apply -f $SKYSHIFT/examples/vllm-demo/vllm.yaml
    ```

    Verify if the job is in running state and the replicas are distributed across cluster1 and cluster2
    ```
    $ skyctl get jobs
    ⠙ Fetching jobs
    NAME    CLUSTER    REPLICAS    RESOURCES         NAMESPACE    STATUS    AGE
    vllm    cluster1   1/1         cpus: 4.0         default      RUNNING   5s
                                   memory: 12.00 GB
                                   L4: 1.0
    vllm    cluster2   1/1         cpus: 4.0         default      RUNNING   5s
                                   memory: 12.00 GB
                                   L4: 1.0
    ✔ Fetching jobs completed successfully.
    ```
5) Create a service for the jobs
    ```
    skyctl apply -f $SKYSHIFT/examples/vllm-demo/vllm_service.yaml 

    ```

    Note: The service is created in Cluster1 as frontend.

6) Now, retrieve the vllm-service's IP

    ```
    skyctl get svc vllm-service
    ```

    ```
    export VLLM_SERVICE='Use the IP address from the above command'
    ```
    
    Alternatively, use the following command to get the IP/host:

    ```
    export FRONTEND_IP=`kubectl get svc vllm-service --context cluster1 -o jsonpath='{.status.loadBalancer.ingress[0].ip}'`
    ```

    Note: Use `.status.loadBalancer.ingress[0].hostname` in the above command if the cloud k8s service allocates hostname instead of IP.
    open http://$FRONTEND_IP/productpage in browser, and you should be able to view the rating/reviews of the book as shown below.

7) Now, test it out

    ```
    curl -X POST "$FRONTEND_IP/v1/chat/completions" \
	-H "Content-Type: application/json" \
	--data '{
		"model": "meta-llama/Llama-3.1-8B-Instruct",
		"messages": [
			{"role": "user", "content": "Sanfrancisco is a "}
		]
	}' | jq
    ```

8) Finally, Cleanup

    ```
    ./cleanup.sh
    ```