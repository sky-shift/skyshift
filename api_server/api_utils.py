"""Utility functions for the API server."""
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
import yaml
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

# Assumes authentication tokens are JWT tokens
OAUTH2_SCHEME = OAuth2PasswordBearer(tokenUrl="token")
API_SERVER_CONFIG_PATH = "~/.skyconf/config.yaml"
CACHED_SECRET_KEY = None


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
        if datetime.now(timezone.utc) >= datetime.fromtimestamp(payload.get("exp"), tz=timezone.utc):  #type: ignore
            raise HTTPException(
                status_code=401,
                detail="Token expired. Please log in again.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except jwt.PyJWTError as error:
        raise credentials_exception from error
    return username


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
