"""
Specifies the API server and its endpoints for Skyflow.
"""
import json
import signal
import sys
from functools import partial

import jsonpatch
import yaml
from fastapi import APIRouter, FastAPI, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from kubernetes import client, config
from skyflow.cluster_manager.kubernetes_manager import K8ConnectionError

from skyflow.cluster_manager.manager_utils import setup_cluster_manager
from skyflow.etcd_client.etcd_client import ETCD_PORT, ETCDClient
from skyflow.globals import (ALL_OBJECTS, DEFAULT_NAMESPACE,
                             NAMESPACED_OBJECTS, NON_NAMESPACED_OBJECTS)
from skyflow.templates import Namespace, NamespaceMeta, ObjectException
from skyflow.templates.event_template import WatchEvent
from skyflow.utils import load_object


class APIServer:
    """
    Defines the API server for the Skyflow.

    It maintains a connection to the ETCD server and provides a REST API for
    interacting with Skyflow objects. Supports CRUD operations on all objects.
    """

    def __init__(self, etcd_port=ETCD_PORT):
        self.etcd_client = ETCDClient(port=etcd_port)
        self.router = APIRouter()
        self._create_endpoints()
        self._post_init_hook()

    def _post_init_hook(self):
        all_namespaces = self.etcd_client.read_prefix("namespaces")
        # Hack: Create Default Namespace if it does not exist.
        if DEFAULT_NAMESPACE not in all_namespaces:
            self.etcd_client.write(
                "namespaces/default",
                Namespace(metadata=NamespaceMeta(name="default")).model_dump(
                    mode="json"),
            )

    def _fetch_etcd_object(self, link_header: str):
        """Fetches an object from the ETCD server."""
        obj_dict = self.etcd_client.read(link_header)
        if obj_dict is None:
            raise HTTPException(
                status_code=404,
                detail=f"Object '{link_header}' not found.",
            )
        return obj_dict
    
    def _check_cluster_connectivity(self, obj_dict):
        try:
            # Load the kubeconfig file for the specified context
            config.load_kube_config(context=obj_dict["metadata"]["name"], persist_config=False)
            
            # Create a client for the CoreV1API
            v1 = client.CoreV1Api()
            # Try to list namespaces as a connectivity check
            v1.list_namespace(timeout_seconds=10)
        except config.ConfigException as error:
            raise HTTPException(
                status_code=400,
                detail=f'Could not load configuration for Kubernetes cluster {obj_dict["metadata"]["name"]}.') from error
        except client.exceptions.ApiException as error:
            raise HTTPException(
                status_code=400,
                detail=f'Could not connect to Kubernetes cluster {obj_dict["metadata"]["name"]}, check connectivity and permissions.') from error
        except Exception as error:  # Catch-all for other exceptions such as network issues
            raise HTTPException(
                status_code=400,
                detail=f'An error occurred while trying to connect to the Kubernetes cluster {obj_dict["metadata"]["name"]}.') from error

    def create_object(self, object_type: str):
        """Creates an object of a given type."""

        async def _create_object(request: Request,
                                 namespace: str = DEFAULT_NAMESPACE):
            content_type = request.headers.get("content-type", None)
            body = await request.body()
            if content_type == "application/json":
                object_specs = json.loads(body.decode())
            elif content_type == "application/yaml":
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
                object_init = object_class(**object_specs)
            except ObjectException as error:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid {object_type} template.") from error

            object_name = object_init.get_name()

            # Read all objects of the same type and check if the object already exists.
            if object_type in NAMESPACED_OBJECTS:
                link_header = f"{object_type}/{namespace}"
            else:
                link_header = object_type
            list_response = self.etcd_client.read_prefix(link_header)
            for obj_dict in list_response:
                temp_name = obj_dict["metadata"]["name"]
                if object_name == temp_name:
                    raise HTTPException(
                        status_code=409,
                        detail=
                        f"Conflict error: Object '{link_header}/{object_name}' already exists.",
                    )
                
            # Check if object type is cluster and if it is accessible.
            if object_type == "clusters":
                self._check_cluster_connectivity(object_specs)

            self.etcd_client.write(f"{link_header}/{object_name}",
                                   object_init.model_dump(mode="json"))
            return object_init

        return _create_object

    def list_objects(
            self,
            object_type: str,
            namespace: str = DEFAULT_NAMESPACE,
            watch: bool = Query(False),
    ):
        """
        Lists all objects of a given type.
        """
        if object_type not in ALL_OBJECTS:
            raise HTTPException(status_code=400,
                                detail=f"Invalid object type: {object_type}")
        object_class = ALL_OBJECTS[object_type]
        if namespace is not None and object_type in NAMESPACED_OBJECTS:
            link_header = f"{object_type}/{namespace}"
        else:
            link_header = f"{object_type}"

        if watch:
            return self._watch_key(link_header)
        read_response = self.etcd_client.read_prefix(link_header)
        obj_cls = object_class.__name__ + "List"
        obj_list = load_object({
            'kind': obj_cls,
            'objects': read_response,
        })
        return obj_list

    def get_object(
            self,
            object_type: str,
            object_name: str,
            namespace: str = DEFAULT_NAMESPACE,
            watch: bool = Query(False),
    ):
        """
        Returns a specific object, raises Error otherwise.
        """
        if object_type not in ALL_OBJECTS:
            raise HTTPException(status_code=400,
                                detail=f"Invalid object type: {object_type}")
        object_class = ALL_OBJECTS[object_type]

        if object_type in NAMESPACED_OBJECTS:
            link_header = f"{object_type}/{namespace}"
        else:
            link_header = f"{object_type}"

        if watch:
            return self._watch_key(f"{link_header}/{object_name}")
        obj_dict = self._fetch_etcd_object(f"{link_header}/{object_name}")
        obj = object_class(**obj_dict)
        return obj

    def update_object(
        self,
        object_type: str,
    ):
        """Updates an object of a given type."""

        async def _update_object(
            request: Request,
            namespace: str = DEFAULT_NAMESPACE,
        ):
            content_type = request.headers.get("content-type", None)
            body = await request.body()
            if content_type == "application/json":
                object_specs = json.loads(body.decode())
            elif content_type == "application/yaml":
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
                obj_instance = object_class(**object_specs)
            except ObjectException as error:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid {object_type} template.") from error

            object_name = obj_instance.get_name()
            # Read all objects of the same type and check if the object already exists.
            if object_type in NAMESPACED_OBJECTS:
                link_header = f"{object_type}/{namespace}"
            else:
                link_header = object_type

            list_response = self.etcd_client.read_prefix(link_header)
            for obj_dict in list_response:
                temp_name = obj_dict["metadata"]["name"]
                if object_name == temp_name:
                    try:
                        self.etcd_client.update(
                            f"{link_header}/{object_name}",
                            obj_instance.model_dump(mode="json"),
                        )
                    except Exception as error:
                        raise HTTPException(
                            status_code=409,
                            detail=
                            f"Conflict Error: Object '{link_header}/{object_name}' is out of date.",
                        ) from error
                    return obj_instance
            raise HTTPException(
                status_code=400,
                detail=f"Object '{link_header}/{object_name}' does not exist.",
            )

        return _update_object

    # Example command:
    # curl -X PATCH  http://127.0.0.1:50051/clusters/local
    # -H 'Content-Type: application/json'
    # -d '[{"op": "replace", "path": "/status/status",
    # "value": "INIT"}]'
    def patch_object(self, object_type: str):
        """Patches an object of a given type."""

        async def _patch_object(
            request: Request,
            object_name: str,
            namespace: str = DEFAULT_NAMESPACE,
        ):
            content_type = request.headers.get("content-type", None)
            body = await request.body()
            if content_type == "application/json":
                patch_list = json.loads(body.decode())
            elif content_type == "application/yaml":
                patch_list = yaml.safe_load(body.decode())
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported Content-Type: {content_type}")

            if object_type not in ALL_OBJECTS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid object type: {object_type}")

            # Read all objects of the same type and check if the object already exists.
            if object_type in NAMESPACED_OBJECTS:
                link_header = f"{object_type}/{namespace}"
            else:
                link_header = f"{object_type}"
            obj_dict = self.etcd_client.read(f"{link_header}/{object_name}")
            if obj_dict is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Object '{link_header}/{object_name}' not found.",
                )

            # Support basic JSON patch: https://jsonpatch.com/
            try:
                patch = jsonpatch.JsonPatch(patch_list)
            except Exception as error:
                raise HTTPException(status_code=400,
                                    detail="Invalid patch list.") from error

            updated_obj_dict = patch.apply(obj_dict)
            object_class = ALL_OBJECTS[object_type]
            obj = object_class(**updated_obj_dict)
            try:
                self.etcd_client.update(
                    f"{link_header}/{object_name}",
                    obj.model_dump(mode="json"),
                )
            except Exception as error:
                raise HTTPException(
                    status_code=409,
                    detail=
                    f"Conflict Error: Object '{link_header}/{object_name}' is out of date.",
                ) from error
            return obj

        return _patch_object

    def job_logs(self, object_name: str, namespace: str = DEFAULT_NAMESPACE):
        """Returns logs for a given job."""
        # Fetch cluster/clusters where job is running.
        job_link_header = f"jobs/{namespace}/{object_name}"
        job_dict = self._fetch_etcd_object(job_link_header)
        job_obj = ALL_OBJECTS["jobs"](**job_dict)
        job_clusters = list(job_obj.status.replica_status.keys())  # pylint: disable=no-member
        total_logs = []
        for cluster_name in job_clusters:
            cluster_link_header = f"clusters/{cluster_name}"
            cluster_dict = self._fetch_etcd_object(cluster_link_header)
            cluster_obj = ALL_OBJECTS["clusters"](**cluster_dict)
            cluster_manager = setup_cluster_manager(cluster_obj)
            total_logs.extend(cluster_manager.get_job_logs(job_obj))
        return total_logs

    def delete_object(
        self,
        object_type: str,
        object_name: str,
        namespace: str = DEFAULT_NAMESPACE,
    ):
        """Deletes an object of a given type."""
        if object_type in NAMESPACED_OBJECTS:
            link_header = f"{object_type}/{namespace}"
        else:
            link_header = f"{object_type}"
        obj_dict = self.etcd_client.delete(f"{link_header}/{object_name}")
        if obj_dict:
            return obj_dict
        raise HTTPException(
            status_code=400,
            detail=f"Object '{link_header}/{object_name}' does not exist.",
        )

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
                    yield watch_event.model_dump_json() + "\n"
            finally:
                cancel_watch_fn()

        return StreamingResponse(generate_events(),
                                 media_type="application/x-ndjson")

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
        for object_type in NON_NAMESPACED_OBJECTS:
            self._add_endpoint(
                endpoint=f"/{object_type}",
                endpoint_name=f"create_{object_type}",
                handler=self.create_object(object_type=object_type),
                methods=["POST"],
            )
            self._add_endpoint(
                endpoint=f"/{object_type}",
                endpoint_name=f"update_{object_type}",
                handler=self.update_object(object_type=object_type),
                methods=["PUT"],
            )
            self._add_endpoint(
                endpoint=f"/{object_type}",
                endpoint_name=f"list_{object_type}",
                handler=partial(self.list_objects, object_type=object_type),
                methods=["GET"],
            )
            self._add_endpoint(
                endpoint=f"/{object_type}/{{object_name}}",
                endpoint_name=f"get_{object_type}",
                handler=partial(self.get_object, object_type=object_type),
                methods=["GET"],
            )
            self._add_endpoint(
                endpoint=f"/{object_type}/{{object_name}}",
                endpoint_name=f"patch_{object_type}",
                handler=self.patch_object(object_type=object_type),
                methods=["PATCH"],
            )
            self._add_endpoint(
                endpoint=f"/{object_type}/{{object_name}}",
                endpoint_name=f"delete_{object_type}",
                handler=partial(self.delete_object, object_type=object_type),
                methods=["DELETE"],
            )

        for object_type in NAMESPACED_OBJECTS:
            self._add_endpoint(
                endpoint=f"/{{namespace}}/{object_type}",
                endpoint_name=f"create_{object_type}",
                handler=self.create_object(object_type=object_type),
                methods=["POST"],
            )
            self._add_endpoint(
                endpoint=f"/{{namespace}}/{object_type}",
                endpoint_name=f"update_{object_type}",
                handler=self.update_object(object_type=object_type),
                methods=["PUT"],
            )
            self._add_endpoint(
                endpoint=f"/{{namespace}}/{object_type}",
                endpoint_name=f"list_{object_type}",
                handler=partial(
                    self.list_objects,
                    object_type=object_type,
                ),
                methods=["GET"],
            )
            self._add_endpoint(
                endpoint=f"/{{namespace}}/{object_type}/{{object_name}}",
                endpoint_name=f"get_{object_type}",
                handler=partial(
                    self.get_object,
                    object_type=object_type,
                ),
                methods=["GET"],
            )
            self._add_endpoint(
                endpoint=f"/{{namespace}}/{object_type}/{{object_name}}",
                endpoint_name=f"delete_{object_type}",
                handler=partial(
                    self.delete_object,
                    object_type=object_type,
                ),
                methods=["DELETE"],
            )
            self._add_endpoint(
                endpoint=f"/{{namespace}}/{object_type}/{{object_name}}",
                endpoint_name=f"patch_{object_type}",
                handler=self.patch_object(object_type=object_type),
                methods=["PATCH"],
            )
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
                methods=["GET"],
            )

        # Job logs
        self._add_endpoint(
            endpoint="/{namespace}/jobs/{object_name}/logs",
            endpoint_name="job_logs",
            handler=self.job_logs,
            methods=["GET"],
        )


def startup():
    """Initialize the API server upon startup."""
    signal.signal(signal.SIGINT, lambda x, y: sys.exit())


app = FastAPI(debug=True)
# Launch the API service with the parsed arguments
api_server = APIServer()
app.include_router(api_server.router)
app.add_event_handler("startup", startup)
