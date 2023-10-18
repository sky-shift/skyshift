from functools import partial
import json

from flask import Flask, jsonify, request, Response
from flask_sockets import Sockets
import yaml

from sky_manager import ETCDClient
from sky_manager.templates import ObjectException
from sky_manager.templates.cluster_template import Cluster, ClusterList, ClusterException
from sky_manager.templates.job_template import Job, JobList, JobException
from sky_manager.templates.event_template import WatchEvent
from sky_manager.utils import ThreadSafeDict

API_SERVICE_PORT = 50051

SUPPORTED_OBJECTS = {
    'clusters': Cluster,
    'jobs': Job,
}


def launch_api_service(port=API_SERVICE_PORT, dry_run=True):
    api_server = APIServer()
    api_server.etcd_client.delete_all()
    if dry_run:
        job_dict = yaml.safe_load(
            open(
                '/home/gcpuser/sky-manager/sky_manager/examples/example_job.yaml',
                "r"))
        for i in range(3):
            api_server.etcd_client.write(
                f'clusters/cluster-{i}',
                json.dumps(
                    dict(
                        Cluster(
                            meta={'name': f'cluster-{i}'},
                            spec={'manager': 'kubernetes'},
                        ))),
            )
            job_dict['metadata']['name'] = f'job-{i}'
            api_server.etcd_client.write(f'jobs/job-{i}', json.dumps(job_dict))
    api_server.run(port=port)


class APIServer(object):
    """
    Defines the API server for the Sky Manager.

    It maintains a connection to the ETCD server and provides a REST API for
    interacting with Sky Manager objects.
    """

    def __init__(self):
        self.etcd_client = ETCDClient()
        self.app = Flask('Sky-Manager-API-Server')
        self.sockets = Sockets(self.app)
        self.host = 'localhost'

        self.job_prefix = 'jobs'
        self.cluster_prefix = 'clusters'
        self.create_endpoints()

        self.watch_dict = ThreadSafeDict()

    def create_object(self, object_type: str):
        content_type = request.headers['Content-Type']
        if content_type == 'application/json':
            object_specs = request.json
        elif content_type == 'application/yaml':
            object_specs = yaml.safe_load(request.data)
        else:
            return jsonify(error="Unsupported Content-Type"), 400

        if object_type not in SUPPORTED_OBJECTS:
            return jsonify(error=f"Invalid object type: {object_type}"), 400

        object_class = SUPPORTED_OBJECTS[object_type]
        try:
            object_template = object_class.from_dict(object_specs)
        except ObjectException as e:
            return jsonify(error=f"Invalid {object_type} template: {e}"), 400

        response = dict(object_template)
        self.etcd_client.write(f'{object_type}/{object_template.meta.name}',
                               json.dumps(response))
        return jsonify(response), 200

    def list_objects(self, object_type: str):
        """
        Lists all objects of a given type.
        """
        if object_type not in SUPPORTED_OBJECTS:
            return jsonify(error=f"Invalid object type: {object_type}"), 400
        object_class = SUPPORTED_OBJECTS[object_type]

        object_list = []
        read_response = self.etcd_client.read_prefix(object_type)
        for _, read_value in read_response:
            object_dict = json.loads(read_value)
            object_list.append(object_class.from_dict(object_dict))
        obj_list_cls = eval(object_class.__name__ + 'List')(object_list)
        response = dict(obj_list_cls)
        return jsonify(response), 200

    def get_object(self, object_type: str, object_name: str):
        """
        Returns a specific object, raises Error otherwise.
        """
        if object_type not in SUPPORTED_OBJECTS:
            return jsonify(error=f"Invalid object type: {object_type}"), 400
        object_class = SUPPORTED_OBJECTS[object_type]

        etcd_response = self.etcd_client.read(f'{object_type}/{object_name}')
        if etcd_response is None:
            return jsonify(
                error=f'Object \'{object_type}/{object_name}\' not found.'
            ), 404
        obj_dict = json.loads(etcd_response[1])
        cluster_obj = dict(object_class.from_dict(obj_dict))
        return jsonify(cluster_obj)

    def delete_object(self, object_type: str, object_name: str):
        etcd_response = self.etcd_client.delete(f'{object_type}/{object_name}')
        if etcd_response:
            return jsonify(
                message=f'Deleted \'{object_type}/{object_name}\'.'), 200
        return jsonify(
            error=f"Failed to delete \'{object_type}/{object_name}\'."), 404

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
        for object_type in SUPPORTED_OBJECTS.keys():
            self.add_endpoint(endpoint=f"/{object_type}",
                              endpoint_name=f"create_{object_type}",
                              handler=partial(self.create_object, object_type),
                              methods=['POST'])
            self.add_endpoint(endpoint=f"/{object_type}",
                              endpoint_name=f"list_{object_type}",
                              handler=partial(self.list_objects, object_type),
                              methods=['GET'])
            self.add_endpoint(endpoint=f"/{object_type}/<object_name>",
                              endpoint_name=f"get_{object_type}",
                              handler=partial(self.get_object, object_type),
                              methods=['GET'])
            self.add_endpoint(endpoint=f"/{object_type}/<object_name>",
                              endpoint_name=f"delete_{object_type}",
                              handler=partial(self.delete_object, object_type),
                              methods=['DELETE'])

        self.add_endpoint(endpoint="/watch/<key>",
                          endpoint_name="watch",
                          handler=self.watch,
                          methods=['POST'])
        self.add_endpoint(endpoint="/watch/<key>",
                          endpoint_name="cancel_watch",
                          handler=self.cancel_watch,
                          methods=['DELETE'])

    def run(self, port=API_SERVICE_PORT, debug=True):
        self.app.run(host=self.host, port=port, debug=debug, threaded=True)


if __name__ == '__main__':
    launch_api_service()