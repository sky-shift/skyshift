# pylint: disable=C0302
"""
Specifies the API server and its endpoints for SkyShift.
"""
import asyncio
import json
import os
import secrets
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from functools import partial
from pathlib import Path
from typing import Dict, List, Optional, cast
from urllib.parse import unquote

import jsonpatch
import jwt
import yaml
from fastapi import (APIRouter, Body, Depends, FastAPI, HTTPException, Query,
                     Request, WebSocket)
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from pydantic import ValidationError

from skyshift.cluster_manager.kubernetes.kubernetes_manager import \
    K8ConnectionError
from skyshift.cluster_manager.manager_utils import setup_cluster_manager
from skyshift.etcd_client.etcd_client import (ETCD_PORT, ConflictError,
                                              ETCDClient, KeyNotFoundError)
from skyshift.globals import (API_SERVER_CONFIG_PATH, DEFAULT_NAMESPACE,
                              SKYCONF_DIR)
from skyshift.globals_object import (ALL_OBJECTS, NAMESPACED_OBJECTS,
                                     NON_NAMESPACED_OBJECTS)
from skyshift.templates import Namespace, NamespaceMeta, ObjectException
from skyshift.templates.cluster_template import Cluster, ClusterStatusEnum
from skyshift.templates.event_template import WatchEvent
from skyshift.templates.job_template import ContainerStatusEnum, TaskStatusEnum
from skyshift.templates.rbac_template import ActionEnum, Role, RoleMeta, Rule
from skyshift.templates.user_template import User, UserList
from skyshift.utils import load_object, sanitize_cluster_name

###  Utility functions for the API server.

# Assumes authentication tokens are JWT tokens
OAUTH2_SCHEME = OAuth2PasswordBearer(tokenUrl="token")
CACHED_SECRET_KEY = None
CONF_FLAG_DIR = '/.tmp/'
WORKER_LOCK_FILE = SKYCONF_DIR + CONF_FLAG_DIR + 'api_server_init.lock'
WORKER_DONE_FLAG = SKYCONF_DIR + CONF_FLAG_DIR + 'api_server_init_done.flag'


def create_jwt(data: dict,
               secret_key: str,
               expires_delta: Optional[timedelta] = None):
    """Creates jwt of DATA based on SECRET_KEY."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # 10 years
        expire = datetime.now(timezone.utc) + timedelta(minutes=315360000)
    to_encode.update({"exp": expire})
    encoded_jwt: str = jwt.encode(to_encode, secret_key, algorithm='HS512')
    return encoded_jwt


def authenticate_jwt(token: str = Depends(OAUTH2_SCHEME)) -> dict:
    """Authenticates if the token is signed by API Server."""
    global CACHED_SECRET_KEY  # pylint: disable=global-statement

    if CACHED_SECRET_KEY is None:
        secret_key = load_manager_config()["api_server"]["secret"]
        CACHED_SECRET_KEY = secret_key
    else:
        secret_key = CACHED_SECRET_KEY
    try:
        payload = jwt.decode(token, secret_key, algorithms=['HS512'])
    except jwt.PyJWTError as error:
        raise error
    return payload


def authenticate_request(token: str = Depends(OAUTH2_SCHEME)) -> str:
    """Authenticates the request using the provided token.

    If the token is valid, the username is returned. Otherwise, an HTTPException is raised."""

    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = authenticate_jwt(token=token)
        username: str = payload.get("sub", None)
        if username is None:
            raise credentials_exception
        # Check if time out
        if datetime.now(timezone.utc) >= datetime.fromtimestamp(
                payload.get("exp"), tz=timezone.utc):  #type: ignore
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


def generate_nonce(length=32):
    """Generates a secure nonce."""
    return secrets.token_hex(length)


CONF_FLAG_DIR = '/.tmp/'
WORKER_LOCK_FILE = SKYCONF_DIR + CONF_FLAG_DIR + 'api_server_init.lock'
WORKER_DONE_FLAG = SKYCONF_DIR + CONF_FLAG_DIR + 'api_server_init_done.flag'


def check_or_wait_initialization():
    """Creates the necessary configuration files"""
    absolute_done_flag = Path(WORKER_DONE_FLAG)
    absolute_lock_file = Path(WORKER_LOCK_FILE)
    if os.path.exists(absolute_done_flag):
        return

    while os.path.exists(absolute_lock_file):
        # Initialization in progress by another worker, wait...
        time.sleep(1)

    if not os.path.exists(absolute_done_flag):
        # This worker is responsible for initialization
        open(absolute_lock_file, 'a').close()
        try:
            api_server.installation_hook()
            open(absolute_done_flag,
                 'a').close()  # Mark initialization as complete
        finally:
            os.remove(absolute_lock_file)


def remove_flag_file():
    """Removes the flag file to indicate that the API server has been shut down."""
    absolute_done_flag = Path(WORKER_DONE_FLAG)
    if os.path.exists(absolute_done_flag):
        os.remove(absolute_done_flag)


# ==============================================================================
###  API Server Code.

# Hashing password
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ADMIN_USER = os.getenv("SKYSHIFT_ADMIN_USR", "admin")
ADMIN_PWD = os.getenv("SKYSHIFT_ADMIN_PASS", "admin")


class APIServer:
    """
    Defines the API server for the SkyShift.

    It maintains a connection to the ETCD server and provides a REST API for
    interacting with SkyShift objects. Supports CRUD operations on all objects.
    """

    def __init__(self, app, etcd_port=ETCD_PORT):  # pylint: disable=redefined-outer-name
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

        # Create admin role.
        admin_role = Role(metadata=RoleMeta(name="admin-role",
                                            namespaces=["*"]),
                          rules=[Rule(resources=["*"], actions=["*"])],
                          users=[ADMIN_USER])

        self.etcd_client.write(
            "roles/admin-role",
            admin_role.dict(),
        )

        # Create reader role (can only read objects).
        reader_role = Role(
            metadata=RoleMeta(name="reader-role", namespaces=["*"]),
            rules=[Rule(resources=["*"], actions=["get", "list"])],
            users=[ADMIN_USER])

        self.etcd_client.write(
            "roles/reader-role",
            reader_role.dict(),
        )

        # Create inviter role.
        inviter_role = Role(
            metadata=RoleMeta(name="inviter-role", namespaces=["*"]),
            rules=[Rule(resources=["user"], actions=["create"])
                   ],  #Create user actually means can create invite to user.
            users=[])

        self.etcd_client.write(
            "roles/inviter-role",
            inviter_role.dict(),
        )

        # Create system admin user and create authentication token.
        admin_invite_nonce = generate_nonce()
        self.etcd_client.write(
            f"invites/{admin_invite_nonce}",
            {
                "used": False,
                "revoked": False,
                "owner": "",
            },
        )

        admin_invite_jwt = create_jwt(
            data={
                "granted_roles":
                [admin_role.get_name(),
                 inviter_role.get_name()],
                "nonce": admin_invite_nonce,
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

        # Create current context if it not populated yet.
        admin_config = load_manager_config()
        current_context = admin_config.get('current_context', None)
        if not current_context:
            admin_config[
                "current_context"] = f'{ADMIN_USER}-{DEFAULT_NAMESPACE}'
            update_manager_config(admin_config)

    def _authenticate_action(self, action: str, user: str, object_type: str,
                             namespace: str) -> bool:
        """Authenticates the role of a user based on intended action."""

        roles = self.etcd_client.read_prefix("roles")
        for role in roles:
            if self._authenticate_action_with_role(action, user, object_type,
                                                   namespace, role):
                return True

        raise HTTPException(
            status_code=401,
            detail="Unauthorized access. User does not have the required role."
        )

    # pylint: disable=too-many-arguments
    @staticmethod
    def _authenticate_action_with_role(action: str, user: str,
                                       object_type: str, namespace: str,
                                       role: Dict) -> bool:
        """Return if USER on perform ACTION based on ROLE."""

        def _verify_subset(key: str, values: List[str]) -> bool:
            return "*" in values or key in values

        if user not in role['users']:
            return False

        is_namespace = object_type in NAMESPACED_OBJECTS
        if is_namespace and not _verify_subset(namespace,
                                               role['metadata']['namespaces']):
            return False

        rules = role['rules']
        for rule in rules:
            if _verify_subset(action, rule['actions']) and _verify_subset(
                    object_type, rule['resources']):
                return True

        return False

    def _authenticate_by_role_name(self, user: str, role_name: str) -> bool:
        """Authenticates the role of a user based on the Role object name. """
        try:
            role = self._fetch_etcd_object(f"roles/{role_name}")
            return self._authenticate_by_role(user, role)
        except Exception as error:  # Catch-all for other exceptions such as network issues
            raise HTTPException(
                status_code=503,
                detail='An error occured while authenticating user') from error

    def _authenticate_by_role(
            self,
            user: str,
            role: Dict,
            assumed_roles: Optional[List[Dict]] = None) -> bool:
        """Authenticates USER have superset of access of the ROLE. """

        if user in role['users']:
            return True

        if not assumed_roles:
            assumed_roles = self._get_all_roles(user)

        rules = role['rules']
        namespaces = role["metadata"]["namespaces"]
        for namespace in namespaces:
            for rule in rules:
                # Check if all actions permitted by RULE is also permitted for USER
                resources = rule["resources"]
                actions = rule["actions"]
                for rsc in resources:
                    for act in actions:
                        if not any(
                                self._authenticate_action_with_role(
                                    act, user, rsc, namespace, assumed_role)
                                for assumed_role in assumed_roles):
                            raise HTTPException(
                                status_code=401,
                                detail=
                                "Unauthorized access. User does not have the required role."
                            )
        return True

    def _authenticate_by_role_names(self, user: str,
                                    role_names: List[str]) -> bool:
        """Authenticates USER have superset of access of the ROLE_NAMES. """
        assumed_roles = self._get_all_roles(user)
        roles = []
        try:
            for role_name in role_names:
                roles.append(self._fetch_etcd_object(f"roles/{role_name}"))
        except Exception as error:  # Catch-all for other exceptions such as network issues
            raise HTTPException(
                status_code=503,
                detail='An error occured while authenticating user') from error

        return all(
            self._authenticate_by_role(user, role, assumed_roles)
            for role in roles)

    def _get_all_roles(self, user: str) -> List[Dict]:
        all_roles = []
        roles = self.etcd_client.read_prefix("roles")
        for role in roles:
            if user in role['users']:
                all_roles.append(role)
        return all_roles

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

    def _login_user(self, username: str, password: str):  # pylint: disable=too-many-locals, too-many-branches
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

        if 'contexts' not in admin_config:
            admin_config['contexts'] = []

        all_namespaces = self.etcd_client.read_prefix("namespaces")
        # Fetch all namespaces that a user is in.
        user_roles = self._get_all_roles(username)
        allowed_namespaces = set()
        for role in user_roles:
            role_namespaces = role['metadata']['namespaces']
            if '*' in role_namespaces:
                allowed_namespaces = {
                    n['metadata']['name']
                    for n in all_namespaces
                }
                break
            allowed_namespaces.update(role_namespaces)

        # Populate config contexts with new (username, namespace) tuples
        for namespace in allowed_namespaces:
            found = False
            for context in admin_config['contexts']:
                if context['user'] == username and context[
                        'namespace'] == namespace:
                    found = True
                    break
            if not found:
                context_dict = {
                    'namespace': namespace,
                    'user': username,
                    'name': f'{username}-{namespace}'
                }
                admin_config['contexts'].append(context_dict)
        update_manager_config(admin_config)
        return access_dict

    # Authentication/RBAC Methods
    # pylint: disable=too-many-branches
    def register_user(self, user: User, invite_token: str = Body(...)):
        """Registers a user into SkyShift."""
        try:
            invite = authenticate_jwt(invite_token)
            if datetime.now(timezone.utc) >= datetime.fromtimestamp(
                    cast(float, invite.get("exp")), tz=timezone.utc):
                raise HTTPException(
                    status_code=401,
                    detail="Invite token expired. Please ask for a new one.",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            #Check invite(nonce) exist
            invite_store = self._fetch_etcd_object(
                f"invites/{invite['nonce']}")
            if invite_store["revoked"] or invite_store["used"]:
                raise HTTPException(
                    status_code=404,
                    detail="Invite is no longer invalid.",
                )

            inviter = invite['inviter']

            # inviter being "" is special user for setting up admin
            if inviter:
                try:
                    self._fetch_etcd_object(f"users/{inviter}")
                except HTTPException as error:
                    invite_store["revoked"] = True
                    self.etcd_client.write(f'invites/{invite.get("nonce")}',
                                           invite_store)
                    raise HTTPException(
                        status_code=404,
                        detail=
                        "Inviter is no longer invalid. Invalidating the invite.",
                    ) from error

                if not self._authenticate_by_role_name(inviter,
                                                       'inviter-role'):
                    raise HTTPException(
                        status_code=404,
                        detail=
                        "Inviter can no longer invite users. Invite status not changed.",
                    )

            invite_store["used"] = True
            self.etcd_client.write(f'invites/{invite.get("nonce")}',
                                   invite_store)

        except HTTPException as error:
            if error.status_code == 404:
                raise HTTPException(
                    status_code=404,
                    detail="Invite is invalid.",
                ) from error
            raise HTTPException(
                status_code=500,
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
                assumed_roles = self._get_all_roles(inviter)
                for granted_role in invite["granted_roles"]:
                    try:
                        role_dict = self._fetch_etcd_object(
                            f"roles/{granted_role}")
                        # inviter being "" is special user for setting up admin
                        if not inviter or self._authenticate_by_role(
                                inviter, role_dict, assumed_roles):
                            role_dict["users"].append(user.username)
                            self.etcd_client.write(
                                f"roles/{granted_role}",
                                role_dict,
                            )
                            role_message += f"Sucessfully added user to role {granted_role}.\n"
                        else:
                            role_message += f"Inviter can no longer added new user to role {granted_role}.\n"  # pylint: disable=C0301
                    except HTTPException as error:
                        role_message += f"Unusual error has occurred when trying to add user to role {granted_role}.\n"  # pylint: disable=C0301

                return {
                    "message":
                    f"User registered successfully. \n{role_message}",
                    "user": user
                }
            raise HTTPException(  # pylint: disable=raise-missing-from
                status_code=500,
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
        # pylint: disable=too-many-locals
        try:
            # Check user exist
            self._fetch_etcd_object(f"users/{username}")
        except HTTPException as error:
            raise HTTPException(
                status_code=400,
                detail="Cannot create invite. User doesn't exist",
            ) from error

        try:
            if not self._authenticate_by_role_name(username, 'inviter-role'):
                raise HTTPException(
                    status_code=401,
                    detail="Not authorized to create invite.",
                )
        except Exception as error:
            raise HTTPException(
                status_code=404,
                detail="Something went wrong when authenticating the user.",
            ) from error

        #Check if all roles are grantable
        #@TODO:(colin): Replace once we introduce group admin
        if not self._authenticate_by_role_names(username, roles):
            raise HTTPException(
                status_code=401,
                detail=
                "Unauthorized access. User does not have the required role.")

        nonce = generate_nonce()
        self.etcd_client.write(f"invites/{nonce}", {
            "used": False,
            "revoked": False,
            "owner": username
        })
        invite_token = create_jwt(
            data={
                "granted_roles": roles,
                "nonce": nonce,
                "inviter": username
            },
            secret_key=load_manager_config()['api_server']['secret'],
        )
        return {
            "message": "invite created successfully",
            "invite": invite_token
        }

    def revoke_invite(self,
                      invite_token: str = Body(..., embed=True),
                      username: str = Depends(authenticate_request)):
        """Invoke invite."""
        try:
            # Check user exist
            self._fetch_etcd_object(f"users/{username}")
        except HTTPException as error:
            raise HTTPException(
                status_code=400,
                detail="Cannot revoke invite. User doesn't exist",
            ) from error

        try:
            invite = authenticate_jwt(invite_token)
            # empty invite['inviter'] means the special startup invite
            if invite['inviter'] != username and invite['inviter']:
                raise HTTPException(
                    status_code=404,
                    detail="You cannot revoke invites not from you.",
                )

            # Check invite(nonce) exist
            invite_store = self._fetch_etcd_object(
                f"invites/{invite['nonce']}")
            used = invite_store["used"]

            invite_store["revoked"] = True
            self.etcd_client.write(f'invites/{invite.get("nonce")}',
                                   invite_store)

        except HTTPException as error:
            if error.status_code == 404:
                raise HTTPException(
                    status_code=404,
                    detail="Revoke request is invalid.",
                ) from error
            raise HTTPException(
                status_code=500,
                detail="Unusual error occurred.",
            ) from error

        return {
            "message":
            f"invite {invite_token} revoked" if not used else
            f"invite {invite_token} revoked but it's used already",
        }

    # General methods over objects.
    def create_object(self, object_type: str):
        """Creates an object of a given type."""

        async def _create_object(request: Request,
                                 namespace: str = DEFAULT_NAMESPACE,
                                 user: str = Depends(authenticate_request)):
            self._authenticate_action(ActionEnum.DELETE.value, user,
                                      object_type, namespace)
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

    async def list_objects(
            self,
            object_type: str,
            namespace: str = DEFAULT_NAMESPACE,
            watch: bool = Query(False),
            user: str = Depends(authenticate_request),
    ):
        """
        Lists all objects of a given type.
        """
        self._authenticate_action(ActionEnum.LIST.value, user, object_type,
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
            return await self._watch_key(link_header)

        read_response = self.etcd_client.read_prefix(link_header)
        obj_cls = object_class.__name__ + "List"
        obj_list = load_object({
            'kind': obj_cls,
            'objects': read_response,
        })
        return obj_list

    async def get_object(
        self,
        object_type: str,
        object_name: str,
        namespace: str = DEFAULT_NAMESPACE,
        watch: bool = Query(False),
        user: str = Depends(authenticate_request),
    ):  # pylint: disable=too-many-arguments
        """
        Gets a specific object, raises Error otherwise.
        """
        self._authenticate_action(ActionEnum.GET.value, user, object_type,
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
            return await self._watch_key(f"{link_header}/{object_name}")

        obj_dict = self._fetch_etcd_object(f"{link_header}/{object_name}")
        obj = object_class(**obj_dict)
        return obj

    async def _watch_key(self, key: str):
        """Watches a set of keys (prefixed by key) from Etcd3 Client."""
        event_queue: asyncio.Queue = asyncio.Queue()
        events_iterator, cancel_watch_fn = self.etcd_client.watch(key)
        loop = asyncio.get_event_loop()

        def watch_etcd_key():
            for event in events_iterator:
                asyncio.run_coroutine_threadsafe(event_queue.put(event), loop)
            # User cancels the watch, or if the watch errors.
            asyncio.run_coroutine_threadsafe(event_queue.put(None), loop)

        executor = ThreadPoolExecutor(max_workers=1)  # pylint: disable=consider-using-with
        loop.run_in_executor(executor, watch_etcd_key)

        async def generate_events():
            """Pops events from event queue and returns WatchEvent objects."""
            while True:
                try:
                    event = await event_queue.get()
                    if event is None:
                        break
                    event_type, event_value = event
                    event_value = load_object(event_value)
                    watch_event = WatchEvent(event_type=event_type.value,
                                             object=event_value)
                    yield watch_event.model_dump_json() + "\n"
                except (ValidationError, Exception):  # pylint: disable=broad-except
                    # If watch errors, cancel watch.
                    break
            cancel_watch_fn()
            yield "{}"

        return StreamingResponse(generate_events(),
                                 media_type="application/x-ndjson",
                                 status_code=200)

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
            self._authenticate_action(ActionEnum.UPDATE.value, user,
                                      object_type, namespace)
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
            self._authenticate_action(ActionEnum.PATCH.value, user,
                                      object_type, namespace)
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
        self._authenticate_action(ActionEnum.GET.value, user, "jobs",
                                  namespace)
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
        self._authenticate_action(ActionEnum.DELETE.value, user, object_type,
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

    async def list_users(self,
                         watch: bool = Query(False),
                         user: str = Depends(authenticate_request)):
        """
        Lists all users.
        """
        self._authenticate_action(ActionEnum.LIST.value, user, "users", "")

        link_header = "users"
        if watch:
            return await self._watch_key(link_header)

        read_response = self.etcd_client.read_prefix(link_header)
        users_list = [User(**user_data) for user_data in read_response]

        obj_list = UserList(users=users_list)

        return obj_list

    async def delete_user(self,
                          user_delete: str,
                          user: str = Depends(authenticate_request)):
        """
        Deletes a user.
        """
        self._authenticate_action(ActionEnum.DELETE.value, user, "users", "")

        link_header = "users"
        try:
            delete_response = self.etcd_client.delete(
                f"{link_header}/{user_delete}")
        except KeyNotFoundError as error:
            raise HTTPException(
                status_code=404,
                detail=f"User '{user_delete}' does not exist.",
            ) from error

        if delete_response:
            return User(**delete_response)
        raise HTTPException(status_code=400)

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

        self._authenticate_action(ActionEnum.UPDATE.value, user, "jobs",
                                  namespace)

        await websocket.accept()

        try:
            job = await self.get_object(object_type="jobs",
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
            cluster_obj = await self.get_object(object_type="clusters",
                                                object_name=cluster,
                                                watch=False,
                                                user=user)
        except HTTPException as error:
            await websocket.send_text(error.detail)
            await websocket.close(code=1003
                                  )  # Close with unsupported data code
            return

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
        # Revoke invite
        self._add_endpoint(
            endpoint="/revoke_invite",
            endpoint_name="revoke_invite",
            handler=self.revoke_invite,
            methods=["POST"],
        )

        # Get user metadata
        self._add_endpoint(
            endpoint="/users",
            endpoint_name="list_users",
            handler=self.list_users,
            methods=["GET"],
        )

        # Delete user
        self._add_endpoint(
            endpoint="/{users}/{user_delete}",
            endpoint_name="delete_user",
            handler=self.delete_user,
            methods=["DELETE"],
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
