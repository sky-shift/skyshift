import os
import sys
import subprocess
projDir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0,f'{projDir}')

import cluster_linkv2 as clusterlink

from skyflow.cluster_manager import Manager, KubernetesManager
sys.path.append(f"{projDir}/skyflow/network/clusterlink")

print(sys.path)
from skyflow.network.clusterlink.demos.utils.kind import cluster
from skyflow.network.clusterlink.demos.iperf3.kind.iperf3_client_start import testIperf3Client

cluster1 = "peer1"
cluster2 = "peer2"

cluster1_service_yaml = f"{projDir}/clusterlink/demos/iperf3/testdata/manifests/iperf3-client/iperf3-client.yaml"
cluster2_service_yaml = f"{projDir}/clusterlink/demos/iperf3/testdata/manifests/iperf3-server/iperf3.yaml"
cluster1_service           = "iperf3-client"
cluster2_service           = "iperf3-server"
destPort                   = 5000


def cleanup():
    # Cleanup any previous clusters
    cl1.deleteCluster()
    cl2.deleteCluster()
    try :
        subprocess.check_output(f"rm -rf kind-{cluster1}", shell=True).decode('utf-8')
    except:
        pass
    try:
        subprocess.check_output(f"rm -rf kind-{cluster2}", shell=True).decode('utf-8')
    except:
        pass
    try:
        subprocess.check_output(f"rm -rf clusterlink/", shell=True).decode('utf-8')
    except:
        pass

if __name__ == '__main__':

    cl1 = cluster(cluster1)
    cl2 = cluster(cluster2)

    cleanup()
    # Create a new cluster
    cl1.createCluster(runBg=True)        
    cl2.createCluster(runBg=False)  


    cluster1_manager= KubernetesManager("kind-"+cluster1)
    cluster2_manager= KubernetesManager("kind-"+cluster2)

    clusterlink.launch_network_fabric()

    print("Lauching Clusterlink network on peer1!\n")
    try:
        clusterlink.launch_network(cluster1_manager)
    except subprocess.CalledProcessError as e:
        print(f"{e.cmd}")
    print("Lauching Clusterlink network on peer2!\n")
    try:
        clusterlink.launch_network(cluster2_manager)
    except subprocess.CalledProcessError as e:
        print(f"{e.cmd}")

    clusterlink.create_link("", cluster1_manager, cluster2_manager)

    # Create iPerf3 micro-services
    cl1.loadService(cluster1_service, "mlabbe/iperf3",f"{cluster1_service_yaml}")
    cl2.loadService(cluster2_service, "mlabbe/iperf3",f"{cluster2_service_yaml}")

    clusterlink.export_service(cluster2_service, cluster2_manager, [destPort])
    clusterlink.import_service(cluster2_service, cluster1_manager, cluster2_manager.cluster_name, [destPort])

    testIperf3Client(cl1, cluster1_service, cluster2_service+"-kind-"+cluster2, destPort)

