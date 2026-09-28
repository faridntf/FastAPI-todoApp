from sqlalchemy import exists
from .models import TaskModel

def exist_task(db, task_title: str, user_id: int)-> bool:
    return db.query(
        exists().where(
        TaskModel.title == task_title,
        TaskModel.user_id_fk == user_id,
        TaskModel.is_completed == False
    )).scalar()