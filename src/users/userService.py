from fastapi import HTTPException,status,Security,Depends
from fastapi.security import APIKeyCookie
from sqlalchemy.orm import Session
from sqlalchemy.sql import and_
from .models import UserModel
from jwt import ExpiredSignatureError,InvalidTokenError
from core import get_db
from .auth.jwt_auth import decode_token


cookie_scheme = APIKeyCookie(
    name="access_token",
    auto_error=False
)

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
            .filter(UserModel.phone_number == data.phone_number)
            .first()
        )
    
    if phone_exist:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="phone number already exists"
        )

def find_user(identifier,db:Session) -> None:
    
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

def get_current_user(
    access_token: str | None = Security(cookie_scheme),
    db: Session = Depends(get_db),
):
    if access_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please login your account"
        )
    try:
        user_id = decode_token(access_token)
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token"
            )
        
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token is expired",
        )
        
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
        )
        
    user = (
        db.query(UserModel)
        .filter(UserModel.id == user_id)
        .one_or_none()
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    if user.is_delete:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="this account is deleted cannot access",
            )
    return user