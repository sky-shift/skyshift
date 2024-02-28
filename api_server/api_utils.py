"""Utility functions for the API server."""
import os
from datetime import datetime, timedelta
from typing import Optional

import jwt
import yaml
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

# Assumes authentication tokens are JWT tokens
OAUTH2_SCHEME = OAuth2PasswordBearer(tokenUrl="token")
API_SERVER_CONFIG_PATH = "~/.skyconf/config.yaml"
CACHED_SECRET_KEY = None


def create_access_token(data: dict,
                        secret_key: Optional[str] = None,
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


def generate_manager_config(host: str, port: int):
    """Generates the API server config file."""
    absolute_path = os.path.expanduser(API_SERVER_CONFIG_PATH)
    # If path exists, check if host and port are identical
    if os.path.exists(absolute_path):
        with open(absolute_path, "r") as config_file:
            config_dict = yaml.safe_load(config_file)

            if (config_dict["api_server"]["host"] == host
                    and config_dict["api_server"]["port"] == port
                    and "secret" in config_dict["api_server"]):
                print("API server config already exists. Skipping generation.")
                return

    config_dict = {
        "api_server": {
            "host": host,
            "port": port,
            "secret": os.urandom(256).hex(),
        },
        "users": [],
    }
    os.makedirs(os.path.dirname(absolute_path), exist_ok=True)
    with open(absolute_path, "w") as config_file:
        yaml.dump(config_dict, config_file)


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
