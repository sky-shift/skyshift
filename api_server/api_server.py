# pylint: disable=C0302
"""
Specifies the API server and its endpoints for Skyflow.
"""
import json
import os
import signal
import sys
import time
from datetime import datetime
from functools import partial
from typing import List
from urllib.parse import unquote

import jsonpatch
import yaml
from api_server.api_utils import authenticate_jwt  # pylint: disable=import-error
from api_server.api_utils import authenticate_request  # pylint: disable=import-error
from api_server.api_utils import create_jwt  # pylint: disable=import-error
from api_server.api_utils import generate_nonce  # pylint: disable=import-error
from api_server.api_utils import load_manager_config  # pylint: disable=import-error
from api_server.api_utils import update_manager_config  # pylint: disable=import-error
from fastapi import (APIRouter, Body, Depends, FastAPI, HTTPException, Query,
                     Request, WebSocket)
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from passlib.context import CryptContext

from skyflow.cluster_manager.kubernetes_manager import K8ConnectionError
from skyflow.cluster_manager.manager_utils import setup_cluster_manager
from skyflow.etcd_client.etcd_client import (ETCD_PORT, ConflictError,
                                             ETCDClient, KeyNotFoundError)
from skyflow.globals_object import (ALL_OBJECTS,
                             NAMESPACED_OBJECTS, NON_NAMESPACED_OBJECTS)
from skyflow.globals import (API_SERVER_CONFIG_PATH, DEFAULT_NAMESPACE)
from skyflow.templates import Namespace, NamespaceMeta, ObjectException
from skyflow.templates.cluster_template import Cluster, ClusterStatusEnum
from skyflow.templates.event_template import WatchEvent
from skyflow.templates.job_template import ContainerStatusEnum, TaskStatusEnum
from skyflow.templates.rbac_template import ActionEnum, Role, RoleMeta, Rule
from skyflow.templates.user_template import User
from skyflow.utils import load_object, sanitize_cluster_name

# Hashing password
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

#@TODO:(acuadron): retrieve these from an environment variable (maybe populate through TF)
ADMIN_USER = "admin"
ADMIN_PWD = "admin"

# Assumes authentication tokens are JWT tokens
OAUTH2_SCHEME = OAuth2PasswordBearer(tokenUrl="token")
CACHED_SECRET_KEY = None


def create_access_token(data: dict,
                        secret_key: str,
                        expires_delta: Optional[timedelta] = None):
    """Creates access token for users."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        # 10 years
        expire = datetime.utcnow() + timedelta(minutes=315360000)
    to_encode.update({"exp": expire})
    encoded_jwt: str = jwt.encode(to_encode, secret_key, algorithm='HS512')
    return encoded_jwt


def authenticate_request(token: str = Depends(OAUTH2_SCHEME)) -> str:
    """Authenticates the request using the provided token.

    If the token is valid, the username is returned. Otherwise, an HTTPException is raised."""
    global CACHED_SECRET_KEY  # pylint: disable=global-statement
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if CACHED_SECRET_KEY is None:
        secret_key = load_manager_config()["api_server"]["secret"]
        CACHED_SECRET_KEY = secret_key
    else:
        secret_key = CACHED_SECRET_KEY
    try:
        payload = jwt.decode(token, secret_key, algorithms=['HS512'])
        username: str = payload.get("sub", None)
        if username is None:
            raise credentials_exception
        # Check if time out
        if datetime.utcnow() >= datetime.fromtimestamp(payload.get("exp")):
            raise HTTPException(
                status_code=401,
                detail="Token expired. Please log in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except jwt.PyJWTError as error:
        raise credentials_exception from error
    return username


def load_manager_config():
    """Loads the API server config file."""
    try:
        with open(os.path.expanduser(API_SERVER_CONFIG_PATH),
                  "r") as config_file:
            config_dict = yaml.safe_load(config_file)
    except FileNotFoundError as error:
        raise Exception(
            f"API server config file not found at {API_SERVER_CONFIG_PATH}."
        ) from error
    return config_dict


def update_manager_config(config: dict):
    """Updates the API server config file."""
    with open(os.path.expanduser(API_SERVER_CONFIG_PATH), "w") as config_file:
        yaml.dump(config, config_file)


class User(BaseModel):
    """Represents a user for SkyFlow."""
    username: str = Field(..., min_length=4, max_length=50, pattern="^[a-zA-Z0-9_]+$")
    email: Optional[EmailStr] = None 
    password: str = Field(..., min_length=5)
    invite: Optional[str] = None


def check_or_wait_initialization():
    """Creates the necessary configuration files"""
    lock_file_path = "/tmp/api_server_init.lock"
    completion_flag_path = "/tmp/api_server_init_done.flag"
    if os.path.exists(completion_flag_path):
        return

    while os.path.exists(lock_file_path):
        # Initialization in progress by another worker, wait...
        time.sleep(1)

    if not os.path.exists(completion_flag_path):
        # This worker is responsible for initialization
        open(lock_file_path, 'a').close()
        try:
            api_server.installation_hook()
            open(completion_flag_path,
                 'a').close()  # Mark initialization as complete
        finally:
            os.remove(lock_file_path)


def remove_flag_file():
    """Removes the flag file to indicate that the API server has been shut down."""
    completion_flag_path = "/tmp/api_server_init_done.flag"
    if os.path.exists(completion_flag_path):
        os.remove(completion_flag_path)


class APIServer:
    """
    Defines the API server for the Skyflow.

    It maintains a connection to the ETCD server and provides a REST API for
    interacting with Skyflow objects. Supports CRUD operations on all objects.
    """

    def __init__(self, app, etcd_port=ETCD_PORT):
        self.app = app
        self.etcd_client = ETCDClient(port=etcd_port)
        self.router = APIRouter()
        self.create_endpoints()

    def installation_hook(self):
        """Primes the API server with default objects and roles."""
        all_namespaces = self.etcd_client.read_prefix("namespaces")
        # Hack: Create Default Namespace if it does not exist.
        if DEFAULT_NAMESPACE not in all_namespaces:
            self.etcd_client.write(
                "namespaces/default",
                Namespace(metadata=NamespaceMeta(name="default")).model_dump(
                    mode="json"),
            )
        # Create system admin user and create authentication token.
        admin_invite = generate_nonce()
        self.etcd_client.write(
            f"invites/{admin_invite}",
            {},
        )

        admin_invite_jwt = create_jwt(
            data={
                "granted_roles": [],
                "invite": admin_invite,
                "inviter": ""
            },
            secret_key=load_manager_config()['api_server']['secret'],
        )

        admin_user = User(username=ADMIN_USER,
                          password=ADMIN_PWD,
                          email='admin@admin.com')
        try:
            self.register_user(admin_user, admin_invite_jwt)
        except HTTPException:  # pylint: disable=broad-except
            pass
        self._login_user(ADMIN_USER, ADMIN_PWD)

        admin_role = Role(metadata=RoleMeta(name="admin-role",
                                            namespaces=["*"]),
                          rules=[Rule(resources=["*"], actions=["*"])],
                          users=[ADMIN_USER])

        self.etcd_client.write(
            "roles/admin-role",
            admin_role.dict(),
        )

        # Create inviter role and add admin.
        inviter_role = Role(
            metadata=RoleMeta(name="inviter-role", namespaces=["*"]),
            rules=[Rule(resources=["user"], actions=["create"])
                   ],  #Create user actually means can create invite to user.
            users=[ADMIN_USER])

        self.etcd_client.write(
            "roles/inviter-role",
            inviter_role.dict(),
        )

    def _authenticate_role(self, action: str, user: str, object_type: str,
                           namespace: str) -> bool:
        """Authenticates the role of a user based on the Role objects."""

        def _verify_subset(key: str, values: List[str]) -> bool:
            return "*" in values or key in values

        is_namespace = object_type in NAMESPACED_OBJECTS
        roles = self.etcd_client.read_prefix("roles")
        for role in roles:
            if user not in role['users']:
                continue
            if is_namespace and not _verify_subset(
                    namespace, role['metadata']['namespaces']):
                continue
            rules = role['rules']
            for rule in rules:
                if _verify_subset(action, rule['actions']) and _verify_subset(
                        object_type, rule['resources']):
                    return True

        raise HTTPException(
            status_code=401,
            detail="Unauthorized access. User does not have the required role."
        )

    def _authenticate_by_role_name(self, user: str, role_name: str) -> bool:
        """Authenticates the role of a user based on the Role object name."""
        try:
            role = self._fetch_etcd_object(f"roles/{role_name}")
        except Exception as error:  # Catch-all for other exceptions such as network issues
            raise HTTPException(
                status_code=400,
                detail='An error occured while authenticating user') from error

        if user in role['users']:
            return True

        raise HTTPException(
            status_code=401,
            detail="Unauthorized access. User does not have the required role."
        )

    def _check_cluster_connectivity(self, cluster: Cluster):  # pylint: disable=no-self-use
        """Checks if the cluster is accessible."""
        try:
            cluster_manager = setup_cluster_manager(cluster)
            cluster_manager.get_cluster_status()
        except K8ConnectionError as error:
            raise HTTPException(
                status_code=400,
                detail=f'Could not load configuration for Kubernetes cluster\
                      {cluster.get_name()}.') from error
        except Exception as error:  # Catch-all for other exceptions such as network issues
            raise HTTPException(
                status_code=400,
                detail=f'An error occurred while trying to connect to cluster\
                     {cluster.get_name()}.') from error

    def _fetch_etcd_object(self, link_header: str):
        """Fetches an object from the ETCD server."""
        obj_dict = self.etcd_client.read(link_header)
        if obj_dict is None or obj_dict == {}:
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
            ) from error
        if not pwd_context.verify(password, user_dict['password']):
            raise HTTPException(
                status_code=400,
                detail="Incorrect username or password",
            )
        access_token = create_jwt(
            data={
                "sub": username,
            },
            secret_key=load_manager_config()['api_server']['secret'],
        )
        access_dict = {'name': username, 'access_token': access_token}
        # Update access token in admin config.
        admin_config = load_manager_config()
        found_user = False
        if 'users' not in admin_config:
            admin_config['users'] = []
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
    def register_user(self, user: User, invite_token: str = Body(...)):
        """Registers a user into Skyflow."""
        try:
            invite = authenticate_jwt(invite_token)
            if datetime.utcnow() >= datetime.fromtimestamp(invite.get("exp")):
                raise HTTPException(
                    status_code=401,
                    detail="Token expired. Please log in again.",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            #Check invite(nonce) exist
            self._fetch_etcd_object(f"invites/{invite['invite']}")

            self.etcd_client.delete(f'invites/{invite.get("invite")}')
        except HTTPException as error:
            if error.status_code == 404:
                raise HTTPException(
                    status_code=404,
                    detail="Invite is invalid.",
                )
            raise HTTPException(
                status_code=400,
                detail="Unusual error occurred.",
            ) from error

        try:
            self._fetch_etcd_object(f"users/{user.username}")
        except HTTPException as error:
            if error.status_code == 404:
                user.password = pwd_context.hash(user.password)
                self.etcd_client.write(
                    f"users/{user.username}",
                    user.model_dump(mode="json"),
                )

                #Add newly created user to all the granted roles
                role_message = ""
                for role in invite["granted_roles"]:
                    try:
                        role_dict = self._fetch_etcd_object(f"roles/{role}")
                        role_dict["users"].append(user.username)
                        self.etcd_client.write(
                            f"roles/{role}",
                            role_dict,
                        )
                        role_message += f"Sucessfully added user to role {role} \n"
                    except HTTPException as error:
                        role_message += f"Unusual error has occurred when trying to add user to role {role} \n"

                return {
                    "message":
                    f"User registered successfully. \n{role_message}",
                    "user": user
                }
            raise HTTPException(
                status_code=400,
                detail="Unusual error occurred.",
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"User '{user.username}' already exists.",
            )

    def login_for_access_token(
        self, form_data: OAuth2PasswordRequestForm = Depends()):
        """Logs in a user and returns an access token."""
        username = form_data.username
        password = form_data.password
        return self._login_user(username, password)

    def create_invite(self,
                      roles: List[str] = Body(..., embed=True),
                      username: str = Depends(authenticate_request)):
        """Create invite for new user and returns the invite jwt."""
        try:
            # Check user exist
            self._fetch_etcd_object(f"users/{username}")
        except HTTPException as error:
            raise HTTPException(
                status_code=400,
                detail="Cannot create invite. User doesn't exist",
            ) from error

        try:
            self._authenticate_by_role_name(username, 'inviter-role')
        except HTTPException as error:
            raise HTTPException(
                status_code=400,
                detail="Not authorized to create invite.",
            ) from error

        #Check if all roles are grantable
        #TODO:(colin): Replace once we introduce group admin
        for to_grant_role_name in roles:
            try:
                role = self._fetch_etcd_object(f"roles/{to_grant_role_name}")
                if username in role['users']:
                    continue
                rules = role['rules']
                namespaces = role["metadata"]["namespaces"]
                for namespace in namespaces:
                    for rule in rules:
                        # Check if all actions permitted by RULE is also permitted for USER
                        resources = rule["resources"]
                        actions = rule["actions"]
                        for rsc in resources:
                            for act in actions:
                                if not self._authenticate_role(
                                        action=act,
                                        user=username,
                                        object_type=rsc,
                                        namespace=namespace):
                                    raise HTTPException(
                                        status_code=401,
                                        detail=
                                        "Unauthorized access. User does not have the required role."
                                    )
            except:
                raise HTTPException(
                    status_code=401,
                    detail=
                    "Unauthorized access. User does not have the required role."
                )

        nonce = generate_nonce()
        self.etcd_client.write(f"invites/{nonce}", {})
        invite_token = create_jwt(
            data={
                "granted_roles": roles,
                "invite": nonce,
                "inviter": username
            },
            secret_key=load_manager_config()['api_server']['secret'],
        )
        return {
            "message": "invite created successfully",
            "invite": invite_token
        }

    # General methods over objects.
    def create_object(self, object_type: str):
        """Creates an object of a given type."""

        async def _create_object(request: Request,
                                 namespace: str = DEFAULT_NAMESPACE,
                                 user: str = Depends(authenticate_request)):
            self._authenticate_role(ActionEnum.DELETE.value, user, object_type,
                                    namespace)
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
            if isinstance(
                    object_init, Cluster
            ) and object_init.status.status == ClusterStatusEnum.READY.value:
                self._check_cluster_connectivity(object_init)

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
        self._authenticate_role(ActionEnum.LIST.value, user, object_type,
                                namespace)
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
    ):  # pylint: disable=too-many-arguments
        """
        Returns a specific object, raises Error otherwise.
        """
        self._authenticate_role(ActionEnum.GET.value, user, object_type,
                                namespace)
        if object_type not in ALL_OBJECTS:
            raise HTTPException(status_code=400,
                                detail=f"Invalid object type: {object_type}")
        object_class = ALL_OBJECTS[object_type]

        if object_type in NAMESPACED_OBJECTS:
            link_header = f"{object_type}/{namespace}"
        else:
            link_header = f"{object_type}"
        if object_type == "clusters":
            object_name = sanitize_cluster_name(object_name)
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
            """Processes request to update an object."""
            self._authenticate_role(ActionEnum.UPDATE.value, user, object_type,
                                    namespace)
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
                    except KeyNotFoundError as error:
                        raise HTTPException(status_code=404,
                                            detail=error.msg) from error
                    except ConflictError as error:
                        raise HTTPException(status_code=409,
                                            detail=error.msg) from error
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
            self._authenticate_role(ActionEnum.PATCH.value, user, object_type,
                                    namespace)
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
            if obj_dict is None or obj_dict == {}:
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
            except KeyNotFoundError as error:
                raise HTTPException(status_code=404,
                                    detail=error.msg) from error
            except Exception as error:
                raise HTTPException(status_code=400, detail=error) from error
            return obj

        return _patch_object

    def job_logs(self,
                 object_name: str,
                 namespace: str = DEFAULT_NAMESPACE,
                 user: str = Depends(authenticate_request)):
        """Returns logs for a given job."""
        self._authenticate_role(ActionEnum.GET.value, user, "jobs", namespace)
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
        user: str = Depends(authenticate_request),
    ):  # pylint: disable=too-many-arguments
        """Deletes an object of a given type."""
        self._authenticate_role(ActionEnum.DELETE.value, user, object_type,
                                namespace)
        if object_type in NAMESPACED_OBJECTS:
            link_header = f"{object_type}/{namespace}"
        else:
            link_header = f"{object_type}"
        if object_type == "clusters":
            object_name = sanitize_cluster_name(object_name)
        try:
            obj_dict = self.etcd_client.delete(f"{link_header}/{object_name}")
        except KeyNotFoundError as error:
            raise HTTPException(
                status_code=404,
                detail=error.msg,
            ) from error
        if obj_dict:
            return obj_dict
        raise HTTPException(
            status_code=400,
            detail=f"Object '{link_header}/{object_name}' does not exist.",
        )

    async def _authenticate_tty_session(
        self, websocket: WebSocket, user: str = Depends(authenticate_request)):
        """
        Authenticates the user initiating a TTY session over WebSocket.

        Args:
            websocket (WebSocket): The active WebSocket connection through which \
                the session is attempted.
            user (str): The username obtained from the authentication token, \
                initially provided by the FastAPI dependency.

        Returns:
            str: The authenticated username, confirming the user is \
                authorized for the TTY session.
        """
        # Extract the token from the WebSocket headers
        token = websocket.headers.get('authorization')
        if token is None or not token.startswith("Bearer "):
            await websocket.close(code=1008
                                  )  # Close with policy violation code
            return

        # Remove "Bearer " from the token
        token = token[7:]

        # Authenticate the user using the token
        try:
            user = authenticate_request(token)
        except HTTPException:
            await websocket.close(code=1008)
            return

        return user

    async def execute_command(  # pylint: disable=too-many-locals disable=too-many-branches disable=too-many-statements
        self,
        websocket: WebSocket,
        user: str = Depends(authenticate_request)):
        """
        Handles a TTY session over WebSocket for executing commands inside a container.

        This method is responsible for setting up and managing a TTY session that allows users to
        execute commands within a specified container of a task. It retrieves execution
        parameters from the WebSocket connection's path parameters, validates the requested action
        against the user's permissions, and forwards the command execution request to the \
            appropriate
        cluster manager.

        Args:
            websocket (WebSocket): The WebSocket connection instance.
            user (str): The username of the user initiating the session, authenticated via a \
                dependency.

        If the specified tasks or container is set to 'None', the method attempts to retrieve \
            default tasks and container
        from the job.

        The method ensures that the user is authorized to perform the update action on the job \
            within the specified namespace
        before proceeding with the command execution.
        """
        user = await self._authenticate_tty_session(websocket, user)

        path_params = websocket.scope['path_params']
        quiet = path_params.get('quiet')
        tty = path_params.get('tty')
        tty = tty == "True"
        resource = path_params.get('resource')
        namespace = path_params.get('namespace')
        tasks = path_params.get('selected_tasks')
        container = path_params.get('container')
        exec_command_json = unquote(
            path_params.get('command').replace("%-2-F-%2-", "/"))
        exec_command = json.loads(exec_command_json)

        self._authenticate_role(ActionEnum.UPDATE.value, user, "jobs",
                                namespace)

        await websocket.accept()

        try:
            job = self.get_object(object_type="jobs",
                                  namespace=namespace,
                                  object_name=resource,
                                  watch=False,
                                  user=user)
        except HTTPException as error:
            await websocket.send_text(error.detail)
            await websocket.close(code=1003)
            return

        # Fetch the cluster where the task is running
        if tasks == "None":
            cluster, tasks = list(job.status.task_status.items())[0]
            tasks = [
                pod_name for pod_name, status in tasks.items()
                if status == TaskStatusEnum.RUNNING.value
            ]
            if len(tasks) == 0:
                close_message = f"No running tasks found for the job '{resource}'."
                await websocket.send_text(close_message)
                await websocket.close(code=1003)
                return
            tasks = tasks[0:1] if tty else tasks
        else:
            cluster_tasks = job.status.task_status
            for cluster_name, tasks_dict in cluster_tasks.items():
                for task_name, status in tasks_dict.items():
                    if task_name == tasks and status == TaskStatusEnum.RUNNING.value:
                        cluster = cluster_name
                        break
        # Check if cluster is accessible and supported.
        try:
            cluster_obj = self.get_object(object_type="clusters",
                                          object_name=cluster,
                                          watch=False,
                                          user=user)
        except HTTPException as error:
            await websocket.send_text(error.detail)
            await websocket.close(code=1003
                                  )  # Close with unsupported data code
            return
        print(cluster_obj.spec.manager)
        if cluster_obj.spec.manager not in ["k8", "kubernetes"]:
            close_message = f"Cluster manager '{cluster_obj.spec.manager}' is not supported."
            await websocket.send_text(close_message)
            await websocket.close(code=1003)
            return
        cluster_manager = setup_cluster_manager(cluster_obj)

        for task in tasks:
            if container == "None":
                if task in job.status.container_status:
                    for container_name, status in job.status.container_status[
                            task].items():
                        if status == ContainerStatusEnum.RUNNING.value:
                            container = container_name  # Run on first running container
                            break
            if quiet == "True":
                await websocket.send_text(
                    "Quiet mode is not supported for TTY sessions. \n")
            await cluster_manager.execute_command(websocket, task, container,
                                                  tty, exec_command)
        if not tty:
            await websocket.close(code=1000)  # Close with normal code

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

    def _add_websocket(self, path=None, endpoint=None, endpoint_name=None):
        self.router.add_websocket_route(
            path=path,
            endpoint=endpoint,
            name=endpoint_name,
        )

    def create_endpoints(self):
        """Creates FastAPI endpoints over different types of objects."""

        for object_type in NON_NAMESPACED_OBJECTS:
            if object_type == "users":
                continue

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
        # Create invite
        self._add_endpoint(
            endpoint="/invite",
            endpoint_name="create_invite",
            handler=self.create_invite,
            methods=["POST"],
        )

        self._add_endpoint(
            endpoint=
            "/{namespace}/exec/{quiet}/{resource}/{selected_tasks}/{container}/{command}",
            endpoint_name="execute_command",
            handler=self.execute_command,
            methods=["POST"],
        )

        self._add_websocket(
            path=
            "/{namespace}/exec/{tty}/{quiet}/{resource}/{selected_tasks}/{container}/{command}",
            endpoint=self.execute_command,
            endpoint_name="execute_command",
        )

        self._add_endpoint(
            endpoint=
            "/{namespace}/exec/{quiet}/{resource}/{selected_tasks}/{container}/{command}",
            endpoint_name="execute_command",
            handler=self.execute_command,
            methods=["POST"],
        )

        self._add_websocket(
            path=
            "/{namespace}/exec/{tty}/{quiet}/{resource}/{selected_tasks}/{container}/{command}",
            endpoint=self.execute_command,
            endpoint_name="execute_command",
        )


def startup():
    """Initialize the API server upon startup."""
    signal.signal(signal.SIGINT, lambda x, y: sys.exit())


app = FastAPI(debug=True)
# Launch the API service with the parsed arguments

api_server = APIServer(app=app)
app.include_router(api_server.router)
app.add_event_handler("startup", startup)
app.add_event_handler("startup", check_or_wait_initialization)
app.add_event_handler("shutdown", remove_flag_file)
