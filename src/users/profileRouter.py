from fastapi import(
    APIRouter,
    Depends,
    status,
    HTTPException,
    Security,
    Response
)

from core import get_db

from sqlalchemy.orm import Session
from sqlalchemy.sql import or_
from .models import UserModel
from .models import ProfileModel
from .userService import check_user_duplicates,find_user


from fastapi.security import OAuth2PasswordRequestForm
from .auth import create_access_token
from .auth.jwt_auth import set_coookie

router = APIRouter(
    prefix="/profile",
    tags=["profile"],
    redirect_slashes=True
)

@router.get("fir")
def hel():
    return "Hello farid"