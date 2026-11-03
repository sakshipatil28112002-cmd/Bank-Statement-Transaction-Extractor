from pydantic import BaseModel, EmailStr, Field
from typing import Optional


# Schema for creating a new user profile
class UserCreate(BaseModel):

    name: str = Field(
        min_length=2,
        max_length=100
    )

    email: EmailStr

    bank_name: str = Field(
        min_length=2,
        max_length=100
    )


# Schema for updating an existing user profile
class UserUpdate(BaseModel):

    name: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=100
    )

    email: Optional[EmailStr] = None

    bank_name: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=100
    )