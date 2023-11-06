from functools import partial
import json
import os
import socket

from flask import Flask, jsonify, request, Response
import yaml

from sky_manager.etcd_client.etcd_client import ETCD_PORT

from sky_manager import ETCDClient
from sky_manager.templates import *
from sky_manager.templates.event_template import WatchEvent

API_SERVER_CONFIG_PATH = '~/.skym/config.yaml'
API_SERVER_HOST = 'localhost'
API_SERVER_PORT = 50051
DEFAULT_NAMESPACE = 'default'
NAMESPACED_OBJECTS = {
    'jobs': Job,
    'filterpolicies': FilterPolicy,
}
NON_NAMESPACED_OBJECTS = {
    'clusters': Cluster,
    'namespaces': Namespace,
}
SUPPORTED_OBJECTS = {**NON_NAMESPACED_OBJECTS, **NAMESPACED_OBJECTS}


def generate_manager_config(host, port):
    config_dict = {
        'api_server': {
            'host': host,
            'port': port,
        },
    }
    absolute_path = os.path.expanduser(API_SERVER_CONFIG_PATH)
    os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
    with open(absolute_path, 'w') as config_file:
        yaml.dump(config_dict, config_file)


def load_manager_config():
    # Read from Sky Manager config file.
    try:
        with open(os.path.expanduser(API_SERVER_CONFIG_PATH),
                  'r') as config_file:
            config_dict = yaml.safe_load(config_file)
        host = config_dict['api_server']['host']
        port = config_dict['api_server']['port']
    except FileNotFoundError as e:
        raise Exception(
            f'API server config file not found at {API_SERVER_CONFIG_PATH}.')
    except KeyError as e:
        raise Exception(
            f'API server config file at {API_SERVER_CONFIG_PATH} is invalid.')
    return host, port


def launch_api_service(host=API_SERVER_HOST,
                       port=API_SERVER_PORT,
                       dry_run=True):
    api_server = APIServer(host=host, port=port)
    if dry_run:
        api_server.etcd_client.delete_all()
        filter_policy_dict = yaml.safe_load(
            open(
                '/home/gcpuser/sky-manager/sky_manager/examples/filter_policy.yaml',
                "r"))
        api_server.etcd_client.write(
            f'filterpolicies/{DEFAULT_NAMESPACE}/no-mluo-cloud',
            json.dumps(filter_policy_dict))
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
            api_server.etcd_client.write(f'jobs/{DEFAULT_NAMESPACE}/job-{i}',
                                         json.dumps(job_dict))
    api_server.run(port=port)


class APIServer(object):
    """
    Defines the API server for the Sky Manager.

    It maintains a connection to the ETCD server and provides a REST API for
    interacting with Sky Manager objects.
    """

    def __init__(self,
                 host: str = API_SERVER_HOST,
                 port=API_SERVER_PORT,
                 etcd_port=ETCD_PORT):
        self.etcd_client = ETCDClient(port=etcd_port)
        self.app = Flask('Sky-Manager-API-Server')
        self.host = host
        self.port = port

        generate_manager_config(self.host, self.port)
        self._create_endpoints()

    def create_object(self,
                      object_type: str,
                      namespace: str = DEFAULT_NAMESPACE,
                      is_namespaced: bool = True):
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

        object_name = object_template.meta.name

        # Read all objects of the same type and check if the object already exists.
        if is_namespaced:
            link_header = f'{object_type}/{namespace}'
        else:
            link_header = object_type

        list_response = self.etcd_client.read_prefix(link_header)
        for obj_key, _ in list_response:
            temp_name = obj_key.split('/')[-1]
            if object_name == temp_name:
                return jsonify(
                    error=
                    f"Object \'{link_header}/{object_name}\' already exists."
                ), 400

        response = dict(object_template)
        self.etcd_client.write(f'{link_header}/{object_name}',
                               json.dumps(response))
        return jsonify(response), 200

    def list_objects(self,
                     object_type: str,
                     namespace: str = DEFAULT_NAMESPACE,
                     is_namespaced: bool = True):
        """
        Lists all objects of a given type.
        """
        watch = request.args.get('watch', default='false').lower() == 'true'

        if object_type not in SUPPORTED_OBJECTS:
            return jsonify(error=f"Invalid object type: {object_type}"), 400
        object_class = SUPPORTED_OBJECTS[object_type]

        object_list = []
        if is_namespaced and namespace is not None:
            link_header = f'{object_type}/{namespace}'
        else:
            link_header = f'{object_type}'

        if watch:
            return self._watch_key(link_header)
        read_response = self.etcd_client.read_prefix(link_header)
        for _, read_value in read_response:
            object_dict = json.loads(read_value)
            object_list.append(object_class.from_dict(object_dict))
        obj_list_cls = eval(object_class.__name__ + 'List')(object_list)
        response = dict(obj_list_cls)
        return jsonify(response), 200

    def get_object(self,
                   object_type: str,
                   object_name: str,
                   namespace: str = DEFAULT_NAMESPACE,
                   is_namespaced: bool = True):
        """
        Returns a specific object, raises Error otherwise.
        """
        watch = request.args.get('watch', default='false').lower() == 'true'

        if object_type not in SUPPORTED_OBJECTS:
            return jsonify(error=f"Invalid object type: {object_type}"), 400
        object_class = SUPPORTED_OBJECTS[object_type]

        if is_namespaced:
            link_header = f'{object_type}/{namespace}'
        else:
            link_header = f'{object_type}'

        if watch:
            return self._watch_key(f'{link_header}/{object_name}')

        etcd_response = self.etcd_client.read(f'{link_header}/{object_name}')
        if etcd_response is None:
            return jsonify(
                error=f'Object \'{link_header}/{object_name}\' not found.'
            ), 404
        obj_dict = json.loads(etcd_response[1])
        cluster_obj = dict(object_class.from_dict(obj_dict))
        return jsonify(cluster_obj)

    def update_object(self,
                      object_type: str,
                      namespace: str = DEFAULT_NAMESPACE,
                      is_namespaced: bool = True):
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

        object_name = object_template.meta.name
        if is_namespaced:
            link_header = f'{object_type}/{namespace}'
        else:
            link_header = f'{object_type}'
        # Read all objects of the same type and find the existing object. If not, return error.
        list_response = self.etcd_client.read_prefix(link_header)
        for obj_key, _ in list_response:
            temp_name = obj_key.split('/')[-1]
            if object_name == temp_name:
                response = dict(object_template)
                self.etcd_client.write(f'{link_header}/{object_name}',
                                       json.dumps(response))
                return jsonify(response), 200
        return jsonify(
            error=f"Object \'{link_header}/{object_name}\' does not exist."
        ), 400

    def delete_object(self,
                      object_type: str,
                      object_name: str,
                      namespace: str = DEFAULT_NAMESPACE,
                      is_namespaced: bool = True):
        if is_namespaced:
            link_header = f'{object_type}/{namespace}'
        else:
            link_header = f'{object_type}'
        etcd_response = self.etcd_client.delete(f'{link_header}/{object_name}')
        if etcd_response:
            return jsonify(
                message=f'Deleted \'{link_header}/{object_name}\'.'), 200
        return jsonify(
            error=f"Failed to delete \'{link_header}/{object_name}\'."), 400

    def _watch_key(self, key: str):
        events_iterator, cancel_watch_fn = self.etcd_client.watch(key)

        def generate_events():
            try:
                for event in events_iterator:
                    event_type, event_key, event_value = event   
                    event_value = json.loads(event_value)
                    watch_event = WatchEvent(
                        event_type.value,
                        event_key,
                        event_value,
                    )
                    watch_event = dict(watch_event)
                    watch_event_str = json.dumps(watch_event)
                    yield f"{watch_event_str}\n"
            finally:
                cancel_watch_fn()

        return Response(generate_events(), content_type='application/x-ndjson')

    def _add_endpoint(self,
                      endpoint=None,
                      endpoint_name=None,
                      handler=None,
                      methods=None):
        self.app.add_url_rule(endpoint,
                              endpoint_name,
                              handler,
                              methods=methods)

    def _create_endpoints(self):
        for object_type in NON_NAMESPACED_OBJECTS.keys():
            self._add_endpoint(endpoint=f"/{object_type}",
                               endpoint_name=f"create_{object_type}",
                               handler=partial(self.create_object,
                                               object_type,
                                               is_namespaced=False),
                               methods=['POST'])
            self._add_endpoint(endpoint=f"/{object_type}",
                               endpoint_name=f"update_{object_type}",
                               handler=partial(self.update_object,
                                               object_type,
                                               is_namespaced=False),
                               methods=['PUT'])
            self._add_endpoint(endpoint=f"/{object_type}",
                               endpoint_name=f"list_{object_type}",
                               handler=partial(self.list_objects,
                                               object_type,
                                               is_namespaced=False),
                               methods=['GET'])
            self._add_endpoint(endpoint=f"/{object_type}/<object_name>",
                               endpoint_name=f"get_{object_type}",
                               handler=partial(self.get_object,
                                               object_type,
                                               is_namespaced=False),
                               methods=['GET'])
            self._add_endpoint(endpoint=f"/{object_type}/<object_name>",
                               endpoint_name=f"delete_{object_type}",
                               handler=partial(self.delete_object,
                                               object_type,
                                               is_namespaced=False),
                               methods=['DELETE'])

        for object_type in NAMESPACED_OBJECTS.keys():
            self._add_endpoint(endpoint=f"/<namespace>/{object_type}",
                               endpoint_name=f"create_{object_type}",
                               handler=partial(
                                   self.create_object,
                                   object_type,
                               ),
                               methods=['POST'])
            self._add_endpoint(endpoint=f"/<namespace>/{object_type}",
                               endpoint_name=f"update_{object_type}",
                               handler=partial(
                                   self.update_object,
                                   object_type,
                               ),
                               methods=['PUT'])
            self._add_endpoint(endpoint=f"/<namespace>/{object_type}",
                               endpoint_name=f"list_{object_type}",
                               handler=partial(
                                   self.list_objects,
                                   object_type,
                               ),
                               methods=['GET'])
            self._add_endpoint(
                endpoint=f"/<namespace>/{object_type}/<object_name>",
                endpoint_name=f"get_{object_type}",
                handler=partial(
                    self.get_object,
                    object_type,
                ),
                methods=['GET'])
            self._add_endpoint(
                endpoint=f"/<namespace>/{object_type}/<object_name>",
                endpoint_name=f"delete_{object_type}",
                handler=partial(
                    self.delete_object,
                    object_type,
                ),
                methods=['DELETE'])
            # Add special case where can list namespaced objects across
            # all namespaces.
            self._add_endpoint(
                endpoint=f"/{object_type}",
                endpoint_name=f"list_{object_type}_all_namespaces",
                handler=partial(
                    self.list_objects,
                    object_type,
                    namespace=None,
                ),
                methods=['GET'])

    def run(self, port, debug=True):
        self.app.run(host=self.host, port=port, debug=debug, threaded=True)


if __name__ == '__main__':
    launch_api_service()