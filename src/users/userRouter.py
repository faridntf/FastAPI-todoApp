from fastapi import(
    APIRouter,
    Depends,
    status,
    HTTPException,
    Security,
    Response,
    Request
)

from .userService import(
    check_user_duplicates,
    find_user
)

from .userSchema import(
    UserCreateSc,
    UserResponseSc,
)

from fastapi.exceptions import ResponseValidationError
from core import get_db
from sqlalchemy.orm import Session
from sqlalchemy.sql import or_
from .models import UserModel
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core import get_db
from .models import UserModel, AuthSession
from .userService import check_user_duplicates, find_user
from .userSchema import UserCreateSc, UserResponseSc, RefreshRequestSc, UserChangePassword
from .auth.jwt_auth import clear_auth_cookies, set_auth_cookies, utcnow
from .auth.session_service import (
    authenticate, start_session, rotate_refresh, lock_user, check_user,
    active_session, claims_or_401, check_csrf, check_origin,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/register", response_model=UserResponseSc, status_code=201)
def create_user(data: UserCreateSc, db: Session = Depends(get_db)):
    check_user_duplicates(db, data)
    user = UserModel(**data.model_dump(exclude={"password", "re_password"}))
    user.set_password(data.password)
    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Username, email or phone number already exists") from None
    return user



@router.post("/login")
def login_user(request: Request, response: Response,
               identifier: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = find_user(identifier.username.strip(), db)
    if user is None or not user.verify_password(identifier.password):
        raise HTTPException(401, "Invalid username or password")
    try:
        tokens, csrf = start_session(db, user, identifier.password)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An active session already exists") from None
    set_auth_cookies(response, tokens, csrf)
    return tokens


@router.post("/login-account")
def login_account(username: OAuth2PasswordRequestForm, db: Session = Depends(get_db)):
    user = find_user()


@router.post("/token/refresh")
def refresh_token(request: Request, response: Response,
                  data: RefreshRequestSc | None = None, db: Session = Depends(get_db),
                  ):
    cookie = request.cookies.get("refresh_token")
    token = cookie or (data.refresh_token if data else None)
    if not token:
        raise HTTPException(401, "Refresh token is required")
    tokens = rotate_refresh(db, token, request, from_cookie=bool(cookie))
    db.commit()
    if cookie:
        set_auth_cookies(response, tokens)
    else:
        response.headers["Cache-Control"] = "no-store"
    return tokens


@router.post("/logout")
def logout_account(requ : Request,response:Response):
    response.delete_cookie(key="access_token",path="/")
    return "Logout successfully"