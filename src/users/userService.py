from fastapi import HTTPException,status
from sqlalchemy.orm import Session
from sqlalchemy.sql import and_
from .models import UserModel

def check_user_duplicates(db: Session, data):
    username_exists = (
        db.query(UserModel)
        .filter(UserModel.username == data.username)
        .first()
    )

    if username_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists"
        )

    email_exists = (
        db.query(UserModel)
        .filter(UserModel.email == data.email)
        .first()
    )

    if email_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists"
        )

    phone_exist = (
            db.query(UserModel)
            .filter(UserModel.username == data.username)
            .first()
        )
    
    if phone_exist:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="phone number already exists"
        )

def find_user(identifier,db:Session):
    
    if "@" in identifier:
        user = db.query(UserModel).where(
            and_(
                UserModel.email == identifier,
                UserModel.is_active == True
            )
        ).one_or_none()
        return user
    
    elif identifier.startswith("09") and identifier.isdigit():
        user = db.query(UserModel).where(
            UserModel.phone_number == identifier,
            UserModel.is_active == True
        ).one_or_none()
        return user
    
    else:
        user = db.query(UserModel).where(
            UserModel.username == identifier,
            UserModel.is_active == True
        ).one_or_none()
        return user
    