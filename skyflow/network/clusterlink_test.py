import argparse
import logging
import os
import shutil
import subprocess
import sys
import time

projDir = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, f'{projDir}')

import cluster_linkv2 as clusterlink

from skyflow.cluster_manager import KubernetesManager, Manager

logging.basicConfig(
    level=logging.INFO,
    format='%(name)s - %(asctime)s - %(levelname)s - %(message)s')

clusterlink_path = os.path.join(clusterlink.CL_DIRECTORY, "clusterlink")
sys.path.append(clusterlink_path)

from demos.iperf3.kind.iperf3_client_start import testIperf3Client

cluster1_service_yaml = f"{clusterlink_path}/demos/iperf3/testdata/manifests/iperf3-client/iperf3-client.yaml"
cluster2_service_yaml = f"{clusterlink_path}/demos/iperf3/testdata/manifests/iperf3-server/iperf3.yaml"
cluster1_service = "iperf3-client"
cluster2_service = "iperf3-server"
destPort = 5000


# cleanCluster removes all deployments and services
def cleanCluster(name: str):
    subprocess.getoutput(f'kubectl config use-context {name}')
    subprocess.getoutput('kubectl delete --all deployments')
    subprocess.getoutput('kubectl delete --all svc')
    subprocess.getoutput('kubectl delete --all pods')
    subprocess.getoutput('kubectl delete --all pvc')
    subprocess.getoutput(
        f'kubectl delete -f {clusterlink.CL_DIRECTORY}/{name}/k8s.yaml')
    subprocess.getoutput(f'kubectl delete -f {cluster1_service_yaml}')
    subprocess.getoutput(f'kubectl delete -f {cluster2_service_yaml}')
    print(f"Cleaned up clusters {name}")


def cleanup(cl1, cl2: str):
    # Cleanup any previous clusters
    cleanCluster(cl1)
    cleanCluster(cl2)

    subprocess.check_output(f"rm -rf {clusterlink.CL_DIRECTORY}/{cl1}",
                            shell=True).decode('utf-8')
    subprocess.check_output(f"rm -rf {clusterlink.CL_DIRECTORY}/{cl2}",
                            shell=True).decode('utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Description of your program')
    parser.add_argument('-e',
                        '--env',
                        help='Script command: kind/ibm',
                        required=False,
                        default="test")
    parser.add_argument('-c',
                        '--command',
                        help='Script command: create/delete/none',
                        required=False,
                        default="test")
    args = vars(parser.parse_args())
    env = args["env"]
    command = args["command"]

    cl1 = None
    cl2 = None
    if env == "kind":
        print("Choosing KIND env")
        from demos.utils.kind import cluster
        cl1 = cluster(name="peer1")
        cl2 = cluster(name="peer2")
    else:
        print("Choosing Cloud env")
        from demos.utils.cloud import cluster
        cl1 = cluster(name="peer1", zone="dal10", platform="ibm")
        cl2 = cluster(name="peer2", zone="dal10", platform="ibm")

    cl1Name = ""
    cl2Name = ""
    if env == "kind":
        cl1Name = "kind-" + cl1.name
        cl2Name = "kind-" + cl2.name
    else:
        cl1Name = cl1.name
        cl2Name = cl2.name

    if command == "delete":
        cl1.deleteCluster()
        cl2.deleteCluster()
        sys.exit(0)
    elif command == "create":
        # Create a new cluster
        cl1.createCluster(runBg=True)
        cl2.createCluster(runBg=False)

        cl1.checkClusterIsReady()
        cl2.checkClusterIsReady()
        sys.exit(0)
    elif command == "cleanup":
        cleanup(cl1Name, cl2Name)
        sys.exit(0)

    cleanup(cl1Name, cl2Name)

    cluster1_manager = KubernetesManager(cl1Name)
    cluster2_manager = KubernetesManager(cl2Name)

    print("Lauching Clusterlink network on peer1!\n")
    try:
        clusterlink.launch_clusterlink(cluster1_manager)
    except subprocess.CalledProcessError as e:
        print(f"{e.cmd}")
    print("Lauching Clusterlink network on peer2!\n")
    try:
        clusterlink.launch_clusterlink(cluster2_manager)
    except subprocess.CalledProcessError as e:
        print(f"{e.cmd}")

    clusterlink.create_link(cluster1_manager, cluster2_manager)

    # Create iPerf3 micro-services
    cl1.loadService(cluster1_service, "mlabbe/iperf3",
                    f"{cluster1_service_yaml}")
    cl2.loadService(cluster2_service, "mlabbe/iperf3",
                    f"{cluster2_service_yaml}")

    clusterlink.export_service(cluster2_service, cluster2_manager, [destPort])
    clusterlink.import_service(cluster2_service, cluster1_manager,
                               cluster2_manager.cluster_name, [destPort])

    testIperf3Client(cl1, cluster1_service, cluster2_service + "-" + cl2Name,
                     destPort)
