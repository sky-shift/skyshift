# Roadmap

This documents directions of interest, inviting community contributions.
* It is not comprehensive ( don't hesitate to propose new features or directions !)
* While some completed features are highlighted, it is not a comprehensive list of all features. 
* If you have questions or ideas, don't hesitate to create and issue, discussion, (or PR)! 


## Observability and Monitoring

### CLI
- [x] aggregate resource summarization
- [x] list jobs
- [x] general support for job inspection via exec

### Graphical Dashboard
Status and availability "at a glance"
- [ ] aggregate available/unavailable-resource summarization 
- [ ] available-resource summarization by resource-group
- [ ] per-job progress (time enqueued, time running, ...) 

### Data collection and export
- [ ] usage statistics to-date
- [ ] historic job completions 
- [ ] historic wait times by resource-group 

## Testing
- [ ] automatic test generation 
- [ ] GitHub action integration


## Cluster Orchestrator Support

### K8s
- [x] automatic cluster detection via kubeconfig
- [x] automatic provisioning option
- [ ] support and test automation for enterprise-grade flavors (e.g. OpenShift) 

### Slurm
- [ ] automatic cluster detection 
- [ ] automatic provisioning option

### Ray
- [ ] automatic cluster detection 
- [ ] automatic provisioning option

### More Orhcestrators

Community contribution and use-cases are welcome!

## Placement optimization
- [ ] Leverage usage statistics and/or historic waiting times in placement decisions (see Observability and Monitoring)

## Storage
- [ ] local file sync (point-to-point)
- [ ] remote file sync (point-to-point)
- [ ] multi-cast (n-to-1) retrieval
- [ ] multi-cast (1-to-n) storage
 
## Use-Case Demonstrations
- [ ] foundation model serving
- [ ] foundation model fine-tuning
- [ ] foundation model pre-training
- [ ] foundation model evaluation
- [ ] multi-cluster (multi-site) data pre-processing
- [ ] seamless multi-server agent development
- [ ] GPU-dependent code development 




