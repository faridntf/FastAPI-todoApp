from sqlalchemy import exists
from .models import CategoriesModel


def category_exists_id(db, category_id: int) -> bool:
    return db.query(
        exists().where(CategoriesModel.id == category_id)
    ).scalar()
    
    
def category_exists_name(db, category_name: str) -> bool:
    return db.query(
        exists().where(CategoriesModel.name == category_name)
    ).scalar()