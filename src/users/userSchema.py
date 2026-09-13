from pydantic import(
    BaseModel,
    Field,
    ConfigDict,
    EmailStr,
    field_validator,
    ValidationInfo
)
from typing import Optional
from datetime import datetime
from .models import EnUserRole


class UserBase(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_]+$"
    )
    
    email: EmailStr
    
    phone_number: Optional[str] = Field(
        default=None,
        max_length=20,
        pattern=r"^\+?[0-9]{10,15}$"
    )
    
    
    model_config = ConfigDict(
        str_strip_whitespace=True
    )
    
class UserResponseSc(UserBase):
    id : int
    
    created_at : datetime
    
    role : EnUserRole
    
    is_active : bool
    
    last_login : Optional[datetime] = Field(default=None)
    
    is_verified : bool
    
    is_profile_completed : bool
    
    
    model_config = ConfigDict(
    from_attributes=True
    )
    
class UserCreateSc(UserBase):
    password: str = Field(
        min_length=8,
        max_length=128
    )
    
    re_password: str = Field(
        min_length=8,
        max_length=128
    )
    
    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not any(char.isupper() for char in value):
            raise ValueError("Password must contain an uppercase letter")
        if not any(char.islower() for char in value):
            raise ValueError("Password must contain a lowercase letter")
        if not any(char.isdigit() for char in value):
            raise ValueError("Password must contain a number")
        return value
    
    @field_validator('re_password')
    @classmethod
    def check_passwords_match(cls, re_password: str, info : ValidationInfo) -> str:
        if not (re_password == info.data.get("password")):
            raise ValueError("password dosen't match")
        return re_password
    
    
    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        extra="forbid"
    )
    
class UserUpdateSc(BaseModel):
    email: EmailStr = Field(default=None)
    
    phone_number: Optional[str] = Field(
            default=None,
            max_length=20,
            pattern=r"^\+?[0-9]{10,15}$"
        )
    
    
    @field_validator("email")
    @classmethod
    def email_cannot_be_empty(cls, value):
        if value is None:
            raise ValueError("email cannot be null")
        return value

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid"
    )
    
class UserChangePassword(BaseModel):
    
    old_password: str = Field(
            min_length=8,
            max_length=128
        )
    new_password: str = Field(
            min_length=8,
            max_length=128
        )
    re_new_password: str = Field(
            min_length=8,
            max_length=128
        )
    
    @field_validator("new_password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not any(char.isupper() for char in value):
            raise ValueError("new_password must contain an uppercase letter")
        if not any(char.islower() for char in value):
            raise ValueError("new_password must contain a lowercase letter")
        if not any(char.isdigit() for char in value):
            raise ValueError("new_password must contain a number")
        return value
    
    @field_validator('re_new_password')
    @classmethod
    def check_passwords_match(cls, re_new_password: str, info : ValidationInfo) -> str:
        if not (re_new_password == info.data.get("new_password")):
            raise ValueError("password dosen't match")
        return re_new_password
    
    
    model_config = ConfigDict(
        extra="forbid"
    )