from fastapi import HTTPException, status, Security, Depends, Request, Header
from .auth.session_service import authenticate
from fastapi.security import APIKeyCookie, HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import or_
from .models import UserModel
from core import get_db


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

    if data.phone_number is None:
        return

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

def find_user(identifier,db:Session) -> UserModel | None:
    users = db.query(UserModel).filter(or_(
        UserModel.username == identifier,
        UserModel.email == identifier,
        UserModel.phone_number == identifier,
    )).limit(2).all()
    if len(users) > 1:
        # A username can equal another account's phone number. Never guess.
        raise HTTPException(400, "Ambiguous login identifier; please use your email")
    return users[0] if users else None

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    access_token: str | None = Security(cookie_scheme),
    authorization: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
):
    return authenticate(request, db).user
