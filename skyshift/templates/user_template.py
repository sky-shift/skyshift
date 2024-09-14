"""User template for SkyShift."""
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class User(BaseModel):
    """Represents a user for SkyShift."""
    username: str = Field(...,
                          min_length=4,
                          max_length=50,
                          pattern="^[a-zA-Z0-9_]+$")
    email: Optional[EmailStr] = None
    password: str = Field(..., min_length=5)


class UserList(BaseModel):
    """Represents a user list for SkyShift."""
    kind: str = "UserList"
    users: List[User]
