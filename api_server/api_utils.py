from datetime import datetime, timedelta
import os
from typing import Optional
import yaml

import jwt
from fastapi import HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer

# Assumes authentication tokens are JWT tokens
OAUTH2_SCHEME = OAuth2PasswordBearer(tokenUrl="token")
API_SERVER_CONFIG_PATH = "~/.skyconf/config.yaml"
CACHED_SECRET_KEY = None

def create_access_token(data: dict, secret_key: Optional[str] = None, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        # 10 years
        expire = datetime.utcnow() + timedelta(minutes=315360000)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm='HS256')
    return encoded_jwt

def authenticate_request(token: str = Depends(OAUTH2_SCHEME)) -> str:
    """Authenticates the request using the provided token.
    
    If the token is valid, the username is returned. Otherwise, an HTTPException is raised."""
    global CACHED_SECRET_KEY
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
        payload = jwt.decode(token, secret_key, algorithms=['HS256'])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        # Check if time out
        if datetime.utcnow() >= datetime.fromtimestamp(payload.get("exp")):
            raise HTTPException(
        status_code=401,
        detail="Token expired. Please log in again.",
        headers={"WWW-Authenticate": "Bearer"},
            )
    except jwt.JWTError:
        raise credentials_exception
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