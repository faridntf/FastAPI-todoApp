from pydantic import(
    BaseModel,
    Field,
    ConfigDict,
    EmailStr,
    field_validator,
    HttpUrl
)
from typing import Optional
from datetime import date
from .models import EnGender






class ProfileBaseSc(BaseModel):
    bio: Optional[str] = Field(
        default=None,
        max_length=1000
    )
    
    profile_url: Optional[HttpUrl] = None
    
    national_id: Optional[str] = Field(
        default=None,
        pattern=r"^\d{10}$"
    )
    
    first_name: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=50
    )
    
    last_name: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=50
    )
    
    date_of_birth: Optional[date] = None
    
    gender: Optional[EnGender] = None
    
    website: Optional[HttpUrl] = None
    
    postal_code: Optional[str] = Field(
        default=None,
        max_length=10
        
    )
    
    address: Optional[str] = Field(
        default=None,
        max_length=1000
    )
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid"
    )

class ProfileCreateSc(ProfileBaseSc):
    first_name: str = Field(
            default=None,
            min_length=2,
            max_length=50
        )
        
    last_name: str = Field(
        default=None,
        min_length=2,
        max_length=50
    )
    
    national_id: str = Field(
        default=None,
        pattern=r"^\d{10}$"
    )
    
class ProfileUpdateSc(ProfileBaseSc):
    pass
    
class ProfileResponseSc(ProfileBaseSc):
    
    user_id_fk : int
    
    model_config = ConfigDict(
        from_attributes=True,
    )