import asyncio
import json
import sys
from asyncio import run
from functools import partial

import yaml
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from skyflow.etcd_client.etcd_client import ETCD_PORT, ETCDClient
from skyflow.globals import (ALL_OBJECTS, DEFAULT_NAMESPACE,
                             NAMESPACED_OBJECTS, NON_NAMESPACED_OBJECTS)
from skyflow.templates import *
from skyflow.templates.event_template import WatchEvent
from skyflow.utils import load_object


def launch_api_service():
    api_server = APIServer()
    return api_server


class APIServer(object):
    """
    Defines the API server for the Sky Manager.

    It maintains a connection to the ETCD server and provides a REST API for
    interacting with Sky Manager objects.
    """

    def __init__(self, etcd_port=ETCD_PORT):
        self.etcd_client = ETCDClient(port=etcd_port)
        self.router = APIRouter()
        self._create_endpoints()
        self._post_init_hook()

    def _post_init_hook(self):
        all_namespaces = self.etcd_client.read_prefix('namespaces')
        # Hack: Create Default Namespace if it does not exist.
        if DEFAULT_NAMESPACE not in all_namespaces:
            self.etcd_client.write(
                'namespaces/default',
                Namespace(metadata=NamespaceMeta(name='default')).model_dump(
                    mode='json'))

    def object_authentication(self):
        return

    def create_object(self, object_type: str):

        async def _create_object(request: Request,
                                 namespace: str = DEFAULT_NAMESPACE):
            content_type = request.headers.get("content-type", None)
            body = await request.body()
            if content_type == 'application/json':
                object_specs = json.loads(body.decode())
            elif content_type == 'application/yaml':
                object_specs = yaml.safe_load(body.decode())
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported Content-Type: {content_type}")

            if object_type not in ALL_OBJECTS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid object type: {object_type}")

            object_class = ALL_OBJECTS[object_type]
            try:
                object = object_class(**object_specs)
            except ObjectException as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid {object_type} template: {e}")

            object_name = object.get_name()
            # Read all objects of the same type and check if the object already exists.
            if object_type in NAMESPACED_OBJECTS:
                link_header = f'{object_type}/{namespace}'
            else:
                link_header = object_type

            list_response = self.etcd_client.read_prefix(link_header)
            for obj_dict in list_response:
                temp_name = obj_dict['metadata']['name']
                if object_name == temp_name:
                    raise HTTPException(
                        status_code=400,
                        detail=
                        f"Object \'{link_header}/{object_name}\' already exists."
                    )
            self.etcd_client.write(f'{link_header}/{object_name}',
                                   object.model_dump(mode='json'))
            return object

        return _create_object

    def list_objects(self,
                     object_type: str,
                     namespace: str = DEFAULT_NAMESPACE,
                     is_namespaced: bool = True,
                     watch: bool = Query(False)):
        """
        Lists all objects of a given type.
        """
        if object_type not in ALL_OBJECTS:
            raise HTTPException(status_code=400,
                                detail=f"Invalid object type: {object_type}")
        object_class = ALL_OBJECTS[object_type]

        object_list = []
        if is_namespaced and namespace is not None:
            link_header = f'{object_type}/{namespace}'
        else:
            link_header = f'{object_type}'

        if watch:
            return self._watch_key(link_header)
        read_response = self.etcd_client.read_prefix(link_header)
        for object_dict in read_response:
            object_list.append(object_class(**object_dict))
        obj_list_cls = eval(object_class.__name__ +
                            'List')(objects=object_list)
        return obj_list_cls

    def get_object(self,
                   object_type: str,
                   object_name: str,
                   namespace: str = DEFAULT_NAMESPACE,
                   is_namespaced: bool = True,
                   watch: bool = Query(False)):
        """
        Returns a specific object, raises Error otherwise.
        """
        if object_type not in ALL_OBJECTS:
            raise HTTPException(status_code=400,
                                detail=f"Invalid object type: {object_type}")
        object_class = ALL_OBJECTS[object_type]

        if is_namespaced:
            link_header = f'{object_type}/{namespace}'
        else:
            link_header = f'{object_type}'

        if watch:
            return self._watch_key(f'{link_header}/{object_name}')
        obj_dict = self.etcd_client.read(f'{link_header}/{object_name}')
        if obj_dict is None:
            raise HTTPException(
                status_code=404,
                detail=f"Object \'{link_header}/{object_name}\' not found.")
        obj = object_class(**obj_dict)
        return obj

    def update_object(
        self,
        object_type: str,
    ):

        async def _update_object(request: Request,
                                 namespace: str = DEFAULT_NAMESPACE,
                                 resource_version: int = Query(None)):
            content_type = request.headers.get("content-type", None)
            body = await request.body()
            if content_type == 'application/json':
                object_specs = json.loads(body.decode())
            elif content_type == 'application/yaml':
                object_specs = yaml.safe_load(body.decode())
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported Content-Type: {content_type}")

            if object_type not in ALL_OBJECTS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid object type: {object_type}")

            object_class = ALL_OBJECTS[object_type]
            try:
                object = object_class(**object_specs)
            except ObjectException as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid {object_type} template: {e}")

            object_name = object.get_name()
            # Read all objects of the same type and check if the object already exists.
            if object_type in NAMESPACED_OBJECTS:
                link_header = f'{object_type}/{namespace}'
            else:
                link_header = object_type

            list_response = self.etcd_client.read_prefix(link_header)
            for obj_dict in list_response:
                temp_name = obj_dict['metadata']['name']
                if object_name == temp_name:
                    try:
                        self.etcd_client.update(f'{link_header}/{object_name}',
                                                object.model_dump(mode='json'))
                    except Exception as e:
                        raise HTTPException(
                            status_code=409,
                            detail=
                            f"Conflict Error: Object \'{link_header}/{object_name}\' is out of date."
                        )
                    return object
            raise HTTPException(
                status_code=400,
                detail=f"Object \'{link_header}/{object_name}\' does not exist."
            )

        return _update_object

    def delete_object(self,
                      object_type: str,
                      object_name: str,
                      namespace: str = DEFAULT_NAMESPACE,
                      is_namespaced: bool = True):
        if is_namespaced:
            link_header = f'{object_type}/{namespace}'
        else:
            link_header = f'{object_type}'
        obj_dict = self.etcd_client.delete(f'{link_header}/{object_name}')
        if obj_dict:
            return obj_dict
        raise HTTPException(
            status_code=400,
            detail=f"Object \'{link_header}/{object_name}\' does not exist.")

    def _watch_key(self, key: str):
        events_iterator, cancel_watch_fn = self.etcd_client.watch(key)

        def generate_events():
            try:
                for event in events_iterator:
                    event_type, event_value = event
                    event_value = load_object(event_value)
                    # Check and validate event type.
                    watch_event = WatchEvent(event_type=event_type.value,
                                             object=event_value)
                    yield watch_event.json() + '\n'
            finally:
                cancel_watch_fn()

        return StreamingResponse(generate_events(),
                                 media_type='application/x-ndjson')

    def _add_endpoint(self,
                      endpoint=None,
                      endpoint_name=None,
                      handler=None,
                      methods=None):
        self.router.add_api_route(
            endpoint,
            handler,
            methods=methods,
            name=endpoint_name,
        )

    def _create_endpoints(self):
        for object_type in NON_NAMESPACED_OBJECTS.keys():
            self._add_endpoint(
                endpoint=f"/{object_type}",
                endpoint_name=f"create_{object_type}",
                handler=self.create_object(object_type=object_type),
                methods=['POST'])
            self._add_endpoint(
                endpoint=f"/{object_type}",
                endpoint_name=f"update_{object_type}",
                handler=self.update_object(object_type=object_type),
                methods=['PUT'])
            self._add_endpoint(endpoint=f"/{object_type}",
                               endpoint_name=f"list_{object_type}",
                               handler=partial(self.list_objects,
                                               object_type=object_type,
                                               is_namespaced=False),
                               methods=['GET'])
            self._add_endpoint(endpoint=f"/{object_type}/{{object_name}}",
                               endpoint_name=f"get_{object_type}",
                               handler=partial(self.get_object,
                                               object_type=object_type,
                                               is_namespaced=False),
                               methods=['GET'])
            self._add_endpoint(endpoint=f"/{object_type}/{{object_name}}",
                               endpoint_name=f"delete_{object_type}",
                               handler=partial(self.delete_object,
                                               object_type=object_type,
                                               is_namespaced=False),
                               methods=['DELETE'])

        for object_type in NAMESPACED_OBJECTS.keys():
            self._add_endpoint(
                endpoint=f"/{{namespace}}/{object_type}",
                endpoint_name=f"create_{object_type}",
                handler=self.create_object(object_type=object_type),
                methods=['POST'])
            self._add_endpoint(
                endpoint=f"/{{namespace}}/{object_type}",
                endpoint_name=f"update_{object_type}",
                handler=self.update_object(object_type=object_type),
                methods=['PUT'])
            self._add_endpoint(endpoint=f"/{{namespace}}/{object_type}",
                               endpoint_name=f"list_{object_type}",
                               handler=partial(
                                   self.list_objects,
                                   object_type=object_type,
                               ),
                               methods=['GET'])
            self._add_endpoint(
                endpoint=f"/{{namespace}}/{object_type}/{{object_name}}",
                endpoint_name=f"get_{object_type}",
                handler=partial(
                    self.get_object,
                    object_type=object_type,
                ),
                methods=['GET'])
            self._add_endpoint(
                endpoint=f"/{{namespace}}/{object_type}/{{object_name}}",
                endpoint_name=f"delete_{object_type}",
                handler=partial(
                    self.delete_object,
                    object_type=object_type,
                ),
                methods=['DELETE'])
            # Add special case where can list namespaced objects across
            # all namespaces.
            self._add_endpoint(
                endpoint=f"/{object_type}",
                endpoint_name=f"list_{object_type}_all_namespaces",
                handler=partial(
                    self.list_objects,
                    object_type=object_type,
                    namespace=None,
                ),
                methods=['GET'])


app = FastAPI(debug=True)
# Launch the API service with the parsed arguments
api_server = launch_api_service()
app.include_router(api_server.router)


@app.on_event("startup")
async def startup_event():
    import signal
    signal.signal(signal.SIGINT, lambda x, y: sys.exit())
