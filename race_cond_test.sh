#!/bin/bash
# THIS SCRIPT IS INTRUSIVE!!!  Run with caution.
# Removes whole directories, see "Clean up working dirs"
# below for details before running script.
#
# To run this script copy it into the root directory
# of SkyShift and then submit the following command:
#    bash race_cond_test.sh
#
# To run the workaround, See WORKAROUND info below. 

# Default arguments
sep="-------------------------------"
#############################################################
# WORKAROUND: See below to setup race condition workaround. #
#############################################################
SHOW_RACE_CONDITION_WORKAROUND="n"
# WORKAROUND: Uncomment below to show race condition workaround in action
#SHOW_RACE_CONDITION_WORKAROUND="y"

cleanup_skyshift() {
  bash launch_skyflow.sh --kill
  sleep 5
}

cleanup_working_dirs() {
  rand=$RANDOM
  echo "mv ~/.etcd ~/etcd.backup.$rand"
  mv ~/.etcd ~/etcd.backup.$rand
  echo "mv ~/.sky ~/sky.backup.$rand"
  mv ~/.sky ~/sky.backup.$rand
  echo "mv ~/.skyconf  ~/skyconf.backup.$rand"
  mv ~/.skyconf  ~/skyconf.backup.$rand
  sleep 2
}

wait_for_skyshift_shutdown() {
  stuff_running=$(ps -ef | grep "launch" | grep -v grep)
  ct=0
  max_ct=25
  echo -n "Waiting for shyshift cleanup to complete..."
  while [[ $stuff_running != "" ]] && [ $ct -lt $max_ct ]
  do
    echo -n "."
    sleep 2
    ct=$(( $ct + 1 ))
    stuff_running=$(ps -ef | grep "launch" | grep -v grep)
  done
  echo " "
  
  if [[ $stuff_running != "" ]]
  then
    echo "Running test output:"
    echo "=========="
    echo "${stuff_running}"
    echo "=========="
    echo "ERROR: System still running please cleanup SkyShift manually"
    exit 1
  fi
}

cleanup() {
  # Cleanup SkyShift
  cleanup_skyshift
  wait_for_skyshift_shutdown
  
  # Clean up working dirs
  cleanup_working_dirs
  
  # Cleanup kind clusters
  kind delete cluster --name abc
  kind delete cluster --name abcd
  sleep 2
  
  # Check system env. for cleanup
  stuff_running=$(ps -ef | grep "etcd \|launch" | grep -v grep)
  ct=0
  max_ct=25
  echo -n "Waiting for cleanup to complete..."
  while [[ $stuff_running != "" ]] && [ $ct -lt $max_ct ]
  do
    echo -n "."
    sleep 2
    ct=$(( $ct + 1 ))
    stuff_running=$(ps -ef | grep "etcd \|launch" | grep -v grep)
  done
  echo " "
  
  if [[ $stuff_running != "" ]]
  then
    echo "Running test output:"
    echo "=========="
    echo "${stuff_running}"
    echo "=========="
    echo "ERROR: System still running please cleanup etcd, SkyShift, kind clusters manually"
    exit 1
  fi
}

# Cleanup env
cleanup 

# Now do some work

# Show latest git commits
echo "${sep}"
echo "git log n 3"
git log --oneline -n 3

# List working dirs
echo "${sep}"
echo "ls -la ~ | grep etcd\|sky" 
ls -la ~ | grep "etcd\|sky"

# Create cluster 1
echo "${sep}"
kind create cluster --name abc
echo "kind create cluster --name abc"
kubectl get pods -A

# Create cluster 2
echo "${sep}"
kind create cluster --name abcd
kubectl get pods -A

if [[ $SHOW_RACE_CONDITION_WORKAROUND == "y" ]]
then
  sleep 20
fi

# Start Skyre
echo "${sep}"
echo "bash launch_skyflow.sh --workers 1"
bash launch_skyflow.sh --workers 1
sleep 15

# Check Skyer
get_clusters=$(skyctl get clusters)
get_clusters_no_headers=$(echo "${get_clusters}"  | grep -v MANAGER)

# Cleanup to ensure output below cleanup is last stdout/stderr
echo "${sep}"
cleanup_skyshift
wait_for_skyshift_shutdown
  
# Now process final output
echo "${sep}"
if [[ $get_clusters_no_headers == "" ]]
then
  echo " "
  echo "#######################################################"
  echo "#                                                     #"
  echo "# See exception above ^^^^ when starting Skyshift.    #"
  echo "#                                                     #"
  echo "# See no clusters listed which issuing command below: #"
  echo "#                                                     #"
  echo "#######################################################"
  echo " "
fi
echo "skyctl get clusters"
echo "${get_clusters}"


