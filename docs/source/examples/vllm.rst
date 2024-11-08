
vLLM Serving Example
==================

This example demonstrates how an application like LLM serving using [vLLM](https://vllm.ai/) can be deployed and scaled using Skyshift
This example uses two k8s clusters with a single node with 1 GPU. We will be deploying two replicas of Llama 3.1 8B model over vLLM, and Skyshift will 
deploy the replicas across two clusters and load balance the requests between the two replicas.

## Pre-requisite

1) Two K8s clusters:
    - Cluster1 with 1 nvidia GPU
    - Cluster2 with 1 nvidia GPU
    For instance, lets assume the GPU type is nvidia L4

.. code-block:: shell

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


1) Start Skyshift using the commands listed in :ref:`Setup Guide <setup>`.

2) Add the two clusters to Skyshift

.. code-block:: shell

    skyctl create cluster --manager k8 cluster1

.. code-block:: shell

    skyctl create cluster --manager k8 cluster2

3) Create a link between the two clusters

.. code-block:: shell

    skyctl create link -s cluster1 -t cluster2 clink


4) Submit the vllm job with two replicas to Skyshift

.. code-block:: shell

    export SKYSHIFT=<Path to cloned Skyshift directory>

Add the HuggingFace Hub token if the model is gated.

.. code-block:: shell

    yq eval '.spec.envs.HUGGING_FACE_HUB_TOKEN = "your_token_value"' -i $SKYSHIFT/examples/vllm-demo/vllm.yaml

Submit the job.

.. code-block:: shell

    skyctl apply -f $SKYSHIFT/examples/vllm-demo/vllm.yaml

.. note::
    Verify if the job is in running state and the replicas are distributed across cluster1 and cluster2

.. code-block:: shell

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

5) Create a service for the vllm job

.. code-block:: shell

    skyctl apply -f $SKYSHIFT/examples/vllm-demo/vllm_service.yaml 

6) Now, retrieve the vllm-service's IP

.. code-block:: shell

    skyctl get svc vllm-service

.. code-block:: shell
    
    export VLLM_SERVICE='Use the IP address from the above command'

.. note::
    
    Alternatively, use the following command to get the IP/host:

    .. code-block:: shell

        export VLLM_SERVICE=`kubectl get svc vllm-service --context cluster1 -o jsonpath='{.status.loadBalancer.ingress[0].ip}'`

    Use `.status.loadBalancer.ingress[0].hostname` in the above command if the cloud k8s service allocates hostname instead of IP.

7) Now, test it out

.. code-block:: shell

    curl -X POST "$VLLM_SERVICE/v1/chat/completions" \
	-H "Content-Type: application/json" \
	--data '{
		"model": "meta-llama/Llama-3.1-8B-Instruct",
		"messages": [
			{"role": "user", "content": "San Francisco is a "}
		]
	}' | jq

8) Finally, Cleanup

.. code-block:: shell

    ./cleanup.sh