#!/bin/bash
kind create cluster --name=cluster1
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.13.10/config/manifests/metallb-native.yaml
sleep 60
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
skyctl create cluster --manager k8 kind-cluster1
sleep 10
skyctl apply -f skyshift/examples/bookinfo-demo/productpage.yaml
skyctl apply -f skyshift/examples/bookinfo-demo/details.yaml
sleep 20
skyctl apply -f skyshift/examples/bookinfo-demo/productpage_service.yaml 
skyctl apply -f skyshift/examples/bookinfo-demo/details_service.yaml 
kind create cluster --name=cluster2
skyctl create cluster --manager k8 kind-cluster2
sleep 10
skyctl apply -f skyshift/examples/bookinfo-demo/ratings.yaml
skyctl apply -f skyshift/examples/bookinfo-demo/reviews.yaml
sleep 30
skyctl create link -s kind-cluster1 -t kind-cluster2 clink
skyctl get jobs
skyctl apply -f skyshift/examples/bookinfo-demo/ratings_service.yaml
skyctl apply -f skyshift/examples/bookinfo-demo/reviews_service.yaml
FRONTEND_IP=`kubectl get svc productpage --context kind-cluster1 -o jsonpath='{.status.loadBalancer.ingress[0].ip}'`
kubectl get pods