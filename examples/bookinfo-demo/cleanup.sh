#!/bin/bash
skyctl delete job details-v1
skyctl delete job productpage
skyctl delete job ratings-v1
skyctl delete job reviews-v2

skyctl delete endpoints details
skyctl delete endpoints productpage
skyctl delete endpoints ratings
skyctl delete endpoints reviews

skyctl delete service details
skyctl delete service productpage
skyctl delete service ratings
skyctl delete service reviews

skyctl delete link clink
skyctl delete cluster kind-cluster1
skyctl delete cluster kind-cluster2
kind delete cluster --name cluster1
kind delete cluster --name cluster2