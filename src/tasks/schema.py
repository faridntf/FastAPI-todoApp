from pydantic import(
    BaseModel,
    Field,
    ConfigDict
)
from typing import Optional
from datetime import datetime
from models import EnTaskGrading

class TaskBase(BaseModel):
    description : Optional[str] = Field(
        default=None,
        max_length=100,
    )
    
    model_config = ConfigDict(
                from_attributes=True,
                str_strip_whitespace=True
                )


class TaskResponseSc(TaskBase):
    id : int
    title : str
    is_completed: bool
    grading : str
    user_id_fk : int
    created_at : datetime
    updated_at : Optional[datetime]
    
    
class TaskCreateSc(TaskBase):
    title : str = Field(
        min_length=1,
        max_length=50
    )
    
    grading : EnTaskGrading = Field(default=EnTaskGrading.medium)
    
    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        extra="forbid"
    )


class TaskUpdateSc(TaskBase):
    
    title : Optional[str] = Field(
        max_length=50
    )
    
    model_config = ConfigDict(
        from_attributes=True,
        str_strip_whitespace=True,
        extra="forbid"
    )