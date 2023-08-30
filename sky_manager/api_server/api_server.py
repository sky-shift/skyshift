import json

from flask import Flask, jsonify, request, Response
from flask_sockets import Sockets
import yaml

from sky_manager import ETCDClient
from sky_manager.templates.cluster_template import Cluster, ClusterList, ClusterCreateException
from sky_manager.templates.job_template import Job, JobList, JobCreateException
from sky_manager.templates.event_template import WatchEvent
from sky_manager.utils import ThreadSafeDict

API_SERVICE_PORT = 50051


def launch_api_service(port=API_SERVICE_PORT, dry_run=True):
    api_server = APIServer()
    api_server.etcd_client.delete_all()
    if dry_run:
        job_dict = yaml.safe_load(
            open(
                '/home/gcpuser/sky-manager/sky_manager/examples/example_job.yaml',
                "r"))
        for i in range(5):
            api_server.etcd_client.write(
                f'clusters/cluster{i}',
                f'{{"kind": "Cluster", "metadata": {{"name": "cluster{i}", "manager_type": "kubernetes"}} }}'
            )
            job_dict['metadata']['name'] = f'job{i}'
            api_server.etcd_client.write(f'jobs/job{i}', json.dumps(job_dict))
    api_server.run(port=port)


class APIServer(object):

    def __init__(self):
        self.etcd_client = ETCDClient()
        self.app = Flask('Sky-Manager-API-Server')
        self.sockets = Sockets(self.app)
        self.host = 'localhost'

        self.job_prefix = 'jobs'
        self.cluster_prefix = 'clusters'
        self.create_endpoints()

        self.watch_dict = ThreadSafeDict()

    def create_cluster(self):
        content_type = request.headers['Content-Type']
        if content_type == 'application/json':
            cluster_specs = request.json
        elif content_type == 'application/yaml':
            cluster_specs = yaml.safe_load(request.data)
        else:
            return jsonify(error="Unsupported Content-Type"), 400
        try:
            cluster_template = Cluster.from_dict(cluster_specs)
        except ClusterCreateException as e:
            return jsonify(error=f"Invalid cluster template: {e}"), 400
        response = dict(cluster_template)
        self.etcd_client.write(
            f'{self.cluster_prefix}/{cluster_template.name}',
            json.dumps(response))
        return jsonify(response), 200

    def list_clusters(self):
        """
        Returns a list of all clusters (ClusterList object).
        """
        read_response = self.etcd_client.read_prefix(self.cluster_prefix)
        cluster_list = []
        if not isinstance(read_response, list):
            read_response = [('', read_response)]
        for read_tup in read_response:
            cluster_dict = json.loads(read_tup[1])
            cluster_list.append(Cluster.from_dict(cluster_dict))
        cluster_list_obj = ClusterList(cluster_list)
        response = dict(cluster_list_obj)
        return jsonify(response), 200

    def get_cluster(self, cluster: str):
        """
        Returns a specific cluster (Cluster object).
        """
        etcd_response = self.etcd_client.read(
            f'{self.cluster_prefix}/{cluster}')
        if etcd_response is None:
            return jsonify(error=f'Cluster \'{cluster}\' not found."'), 404
        cluster_dict = json.loads(etcd_response[1])
        # Verify dict can be converted into Cluster object.
        cluster_obj = dict(Cluster.from_dict(cluster_dict))
        return jsonify(cluster_obj)

    def delete_cluster(self, cluster: str):
        etcd_response = self.etcd_client.delete(
            f'{self.cluster_prefix}/{cluster}')
        if etcd_response:
            return jsonify(message=f'Deleted \'{cluster}\'.'), 200
        return jsonify(error=f"Failed to delete \'{cluster}\'."), 404

    def create_job(self):
        content_type = request.headers['Content-Type']
        if content_type == 'application/json':
            job_specs = request.json
        elif content_type == 'application/yaml':
            job_specs = yaml.safe_load(request.data)
        else:
            return jsonify(error="Unsupported Content-Type"), 400
        try:
            job_template = Job.from_dict(job_specs)
        except JobCreateException as e:
            return jsonify(error=f"Invalid cluster template: {e}"), 400
        response = dict(job_template)
        self.etcd_client.write(f'{self.job_prefix}/{job_template.name}',
                               json.dumps(response))
        return jsonify(response), 200

    def list_jobs(self):
        """
        Returns a list of all submitted jobs (JobList object).
        """
        read_response = self.etcd_client.read_prefix(self.job_prefix)
        job_list = []
        if not isinstance(read_response, list):
            read_response = [('', read_response)]
        for read_tup in read_response:
            job_dict = json.loads(read_tup[1])
            job_list.append(Job.from_dict(job_dict))
        job_list_obj = JobList(job_list)
        response = dict(job_list_obj)
        return jsonify(response), 200

    def get_job(self, job: str):
        """
        Returns a specific job (Job object).
        """
        etcd_response = self.etcd_client.read(f'{self.job_prefix}/{job}')
        if etcd_response is None:
            return jsonify(error=f'Job \'{job}\' not found."'), 404
        job_dict = json.loads(etcd_response[1])
        # Verify dict can be converted into Cluster object.
        job_obj = dict(Job.from_dict(job_dict))
        return jsonify(job_obj)

    def delete_job(self, job: str):
        etcd_response = self.etcd_client.delete(f'{self.job_prefix}/{job}')
        if etcd_response:
            return jsonify(message=f'Deleted \'{job}\'.'), 200
        return jsonify(error=f"Failed to delete \'{job}\'."), 404

    def watch(self, key):
        events_iterator, cancel = self.etcd_client.watch(key)
        self.watch_dict.set(key, cancel)

        def generate_events():
            try:
                for event in events_iterator:
                    event_type = str(type(event))
                    if 'Put' in event_type:
                        event_type = 'Added'
                    elif 'Delete' in event_type:
                        event_type = 'Deleted'
                    else:
                        event_type = 'Unknown'
                    watch_event = WatchEvent(
                        event_type,
                        event.key.decode('utf-8').split('/')[-1],
                        event.value.decode('utf-8'),
                    )
                    watch_event = dict(watch_event)
                    watch_event_str = json.dumps(watch_event)
                    yield f"{watch_event_str}\n"
            finally:
                cancel()

        return Response(generate_events(), content_type='application/x-ndjson')

    def cancel_watch(self, key):
        cancel_watch = self.watch_dict.get(key)
        cancel_watch()
        self.watch_dict.delete(key)
        return ('', 404)

    def add_endpoint(self,
                     endpoint=None,
                     endpoint_name=None,
                     handler=None,
                     methods=None):
        self.app.add_url_rule(endpoint,
                              endpoint_name,
                              handler,
                              methods=methods)

    def create_endpoints(self):
        self.add_endpoint(endpoint="/clusters",
                          endpoint_name="create_cluster",
                          handler=self.create_cluster,
                          methods=['POST'])
        self.add_endpoint(endpoint="/clusters",
                          endpoint_name="list_clusters",
                          handler=self.list_clusters,
                          methods=['GET'])
        self.add_endpoint(endpoint="/clusters/<cluster>",
                          endpoint_name="get_cluster",
                          handler=self.get_cluster,
                          methods=['GET'])
        self.add_endpoint(endpoint="/clusters/<cluster>",
                          endpoint_name="delete_cluster",
                          handler=self.delete_cluster,
                          methods=['DELETE'])
        self.add_endpoint(endpoint="/jobs",
                          endpoint_name="create_job",
                          handler=self.create_job,
                          methods=['POST'])
        self.add_endpoint(endpoint="/jobs",
                          endpoint_name="list_jobs",
                          handler=self.list_jobs,
                          methods=['GET'])
        self.add_endpoint(endpoint="/jobs/<job>",
                          endpoint_name="get_job",
                          handler=self.get_job,
                          methods=['GET'])
        self.add_endpoint(endpoint="/jobs/<job>",
                          endpoint_name="delete_job",
                          handler=self.delete_job,
                          methods=['DELETE'])
        self.add_endpoint(endpoint="/watch/<key>",
                          endpoint_name="watch",
                          handler=self.watch,
                          methods=['POST'])
        self.add_endpoint(endpoint="/watch/<key>",
                          endpoint_name="cancel_watch",
                          handler=self.cancel_watch,
                          methods=['DELETE'])

    def run(self, port=API_SERVICE_PORT):
        self.app.run(host=self.host, port=port, debug=True, threaded=True)


if __name__ == '__main__':
    launch_api_service()