from fastapi import(
    APIRouter,
    Depends,
    status,
    HTTPException,
)

from .schema import(
    TaskCreateSc,
    TaskResponseSc,
    TaskUpdateSc
)

from users import(
    UserModel,
    get_current_user,
    EnUserRole
)

from .models import TaskModel
from .services import exist_task
from core import get_db
from sqlalchemy.orm import Session
from sqlalchemy import exists # result=> True or False
from categories import category_exists_id
from typing import List


router = APIRouter(
    prefix="/tasks",
    tags=["tasks"],
    redirect_slashes=True
)

@router.post("/create",response_model=TaskResponseSc,status_code=status.HTTP_201_CREATED)
def create_new_task(
    data:TaskCreateSc,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    new_task = data.model_dump()
    set_task = TaskModel(**new_task)
    set_task.user_id_fk = current_user.id
    
    exist_category = category_exists_id(db=db,category_id = set_task.category_id_fk)
    if exist_category == False:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="category id is invalid, please check the category id"
        )
    exist_title_for_task_user = exist_task(db=db,task_title=set_task.title,user_id=current_user.id)
    if exist_title_for_task_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,detail="this Task is already exist!!!")
    db.add(set_task)
    db.commit()
    db.refresh(set_task)
    return set_task
    
    

@router.get("/list-tasks")
def get_list_tasks(
    limit:int,
    offset:int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    my_tasks = db.query(TaskModel).where(
        TaskModel.user_id_fk == current_user.id
    ).limit(limit).offset(offset).all()
    return my_tasks


@router.get("/all_tasks")
def get_all_tasks(
    limit:int,
    offset:int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    if current_user.role == EnUserRole.ADMIN:
        my_tasks = db.query(TaskModel).where(
            TaskModel.user_id_fk == current_user.id
        ).limit(limit).offset(offset).all()
        return my_tasks
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Oooops!!!!, just admin users access the section"
        )


@router.get("/task-name")
def get_task_by_name(
    task_name: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    pass

@router.get("/task-id/{task_id}")
def get_task_by_name(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    pass

@router.patch("/update-task/{task_id}")
def create_new_task(
    task_id:int,
    data:TaskUpdateSc,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    pass

@router.delete("/task/{task_id}")
def create_new_task(
    task_id:int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    pass

@router.delete("/task/{task_name}")
def create_new_task(
    task_name:str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    pass

@router.get("/search-task/")
def create_new_task(
    data:TaskCreateSc,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    pass

@router.get("/complete-tasks")
def complete_tasks(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    pass

@router.get("/incomplete")
def incomplete_tasks(
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    pass

@router.get("/get-task-by-category")
def task_by_category(
    data:TaskCreateSc,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    pass

