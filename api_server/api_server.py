"""
Specifies the API server and its endpoints for Skyflow.
"""
import json
import signal
import sys
from functools import partial
from typing import List

import jsonpatch
import yaml
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from pydantic import BaseModel

from skyflow.cluster_manager.manager_utils import setup_cluster_manager
from skyflow.etcd_client.etcd_client import ETCD_PORT, ETCDClient
from skyflow.globals import (ALL_OBJECTS, DEFAULT_NAMESPACE,
                             NAMESPACED_OBJECTS, NON_NAMESPACED_OBJECTS)
from skyflow.templates import Namespace, NamespaceMeta, ObjectException
from skyflow.templates.event_template import WatchEvent
from skyflow.utils import load_object
from api_utils import create_access_token, load_manager_config, update_manager_config, authenticate_request

# Hashing password
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class User(BaseModel):
    """Represents a user for SkyFlow."""
    username: str
    email: str
    password: str


class APIServer:
    """
    Defines the API server for the Skyflow.

    It maintains a connection to the ETCD server and provides a REST API for
    interacting with Skyflow objects. Supports CRUD operations on all objects.
    """
    def __init__(self, etcd_port=ETCD_PORT):
        self.etcd_client = ETCDClient(port=etcd_port)
        self.router = APIRouter()
        self.create_endpoints()
        self.installation_hook()

    def installation_hook(self):
        all_namespaces = self.etcd_client.read_prefix("namespaces")
        # Hack: Create Default Namespace if it does not exist.
        if DEFAULT_NAMESPACE not in all_namespaces:
            self.etcd_client.write(
                "namespaces/default",
                Namespace(metadata=NamespaceMeta(name="default")).model_dump(
                    mode="json"),
            )
        # Create system admin user and create authentication token.
        admin_user = User(username= 'admin', password = 'admin', email= 'N/A')
        try:
            self.register_user(admin_user)
        except Exception: # pylint: disable=broad-except
            pass
        self._login_user(admin_user.username, admin_user.password)
        # Create roles for admin.
        roles_dict = {
            "kind": "Role",
            "metadata": {
                "name": "admin-role",
                "namespaces": ["*"],
            },
            "rules": [
                {
                    "resources": ["*"],
                    "actions": ["*"],
                },
            ],
            "users": [
                "admin",
            ]
        }
        # turn roles_dict into json dict
        roles_json = json.dumps(roles_dict)
        self.etcd_client.write(
            "roles/admin-role",
            roles_json,
        )

    def _authenticate_role(self, action: str, user: str, object_type: str, namespace: str) -> bool:
        def _verify_subset(key: str, values: List[str]) -> bool:
            return "*" in values or key in values
        is_namespace = object_type in NAMESPACED_OBJECTS
        roles = self.etcd_client.read_prefix("roles")

        for role in roles:
            if user not in role['users']:
                continue
            if is_namespace and not _verify_subset(namespace, role['metadata']['namespaces']):
                continue
            rules = role['rules']
            for rule in rules:
                if _verify_subset(action, rule['actions']) and _verify_subset(object_type, rule['resources']):
                    return True

        raise HTTPException(status_code=401, detail="Unauthorized access")

    def _fetch_etcd_object(self, link_header: str):
        """Fetches an object from the ETCD server."""
        obj_dict = self.etcd_client.read(link_header)
        if obj_dict is None:
            raise HTTPException(
                status_code=404,
                detail=f"Object '{link_header}' not found.",
            )
        return obj_dict

    def _login_user(self, username: str, password: str):
        """Helper method that logs in a user."""
        try:
            user_dict = self._fetch_etcd_object(f"users/{username}")
        except HTTPException as error:
            raise HTTPException(
                status_code=400,
                detail="Incorrect username or password",
            )
        if not pwd_context.verify(password, user_dict['password']):   
            raise HTTPException(
                status_code=400,
                detail="Incorrect username or password",
            )
        access_token = create_access_token(
            data={"sub": username, 'password': password},
            secret_key= load_manager_config()['api_server']['secret'],
        )
        access_dict = {'name': username, 'access_token': access_token}
        # Update access token in admin config.
        admin_config = load_manager_config()
        found_user = False
        for user in admin_config['users']:
            if user['name'] == username:
                user['access_token'] = access_token
                found_user = True
                break
        if not found_user:
            admin_config['users'].append(access_dict)
        update_manager_config(admin_config)
        return access_dict

    # Authentication/RBAC Methods
    def register_user(self, user: User):
        """Registers a user into Skyflow."""
        try:
            self._fetch_etcd_object(f"users/{user.username}")
        except HTTPException as error:
            if error.status_code == 404:
                user.password = pwd_context.hash(user.password)
                self.etcd_client.write(
                    f"users/{user.username}",
                    user.model_dump(mode="json"),
                )
                return {"message": "User registered successfully", "user": user}
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Unusual error occurred.",
                )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"User '{user.username}' already exists.",
            )


    def login_for_access_token(self, form_data: OAuth2PasswordRequestForm = Depends()):
        """Logs in a user and returns an access token."""
        username = form_data.username
        password = form_data.password
        return self._login_user(username, password)

    # General methods over objects.
    def create_object(self, object_type: str):
        """Creates an object of a given type."""

        async def _create_object(request: Request,
                                 namespace: str = DEFAULT_NAMESPACE,
                                 user: str = Depends(authenticate_request)):
            self._authenticate_role("create", user, object_type, namespace)
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
            self.etcd_client.write(f"{link_header}/{object_name}",
                                   object_init.model_dump(mode="json"))
            return object_init

        return _create_object

    def list_objects(
            self,
            object_type: str,
            namespace: str = DEFAULT_NAMESPACE,
            watch: bool = Query(False),
            user: str = Depends(authenticate_request),
    ):
        """
        Lists all objects of a given type.
        """
        self._authenticate_role("list", user, object_type, namespace)
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
            user: str = Depends(authenticate_request),
    ):
        """
        Returns a specific object, raises Error otherwise.
        """
        self._authenticate_role("get", user, object_type, namespace)
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
            user: str = Depends(authenticate_request),
        ):
            self._authenticate_role("update", user, object_type, namespace)
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
            user: str = Depends(authenticate_request),
        ):
            self._authenticate_role("patch", user, object_type, namespace)
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

    def job_logs(self, object_name: str, namespace: str = DEFAULT_NAMESPACE, user: str = Depends(authenticate_request)):
        """Returns logs for a given job."""
        self._authenticate_role("get", user, "jobs", namespace)
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
        request: Request,
        object_type: str,
        object_name: str,
        namespace: str = DEFAULT_NAMESPACE,
        user: str = Depends(authenticate_request),
    ):
        """Deletes an object of a given type."""
        self._authenticate_role("delete", user, object_type, namespace)
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

    def create_endpoints(self):
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
        # Register User
        self._add_endpoint(
            endpoint="/register_user",
            endpoint_name="register_user",
            handler=self.register_user,
            methods=["POST"],
        )
        # Login for users to receive their access tokens
        self._add_endpoint(
            endpoint="/token",
            endpoint_name="login_for_access_token",
            handler=self.login_for_access_token,
            methods=["POST"],
        )


def startup():
    """Initialize the API server upon startup."""
    signal.signal(signal.SIGINT, lambda x, y: sys.exit())


app = FastAPI(debug=True)
# Launch the API service with the parsed arguments

api_server = APIServer()
app.include_router(api_server.router)
app.add_event_handler("startup", startup)
