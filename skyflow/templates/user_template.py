"""User template for Skyflow."""
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field

class User(BaseModel):
    """Represents a user for SkyFlow."""
    username: str = Field(..., min_length=4, max_length=50, pattern="^[a-zA-Z0-9_]+$")
    email: Optional[EmailStr] = None 
    password: str = Field(..., min_length=5)
