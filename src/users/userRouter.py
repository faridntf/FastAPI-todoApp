from fastapi import APIRouter, Depends, HTTPException, Request, Response, Header
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


@router.post("/login2", deprecated=True, include_in_schema=False)
@router.post("/login")
def login_user(request: Request, response: Response,
               identifier: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    check_origin(request)
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


@router.post("/token/refresh")
def refresh_token(request: Request, response: Response,
                  data: RefreshRequestSc | None = None, db: Session = Depends(get_db),
                  csrf_token: str | None = Header(default=None, alias="X-CSRF-Token")):
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
def logout_account(request: Request, response: Response, db: Session = Depends(get_db),
                   csrf_token: str | None = Header(default=None, alias="X-CSRF-Token")):
    authorization = request.headers.get("authorization", "")
    bearer = authorization.lower().startswith("bearer ")
    candidates = ([(authorization[7:].strip(), "access")] if bearer else [
        (request.cookies.get("refresh_token"), "refresh"),
        (request.cookies.get("access_token"), "access"),
    ])
    for token, kind in candidates:
        if not token:
            continue
        try:
            claims = claims_or_401(token, kind)
        except HTTPException:
            continue  # Try the access cookie if the refresh cookie is invalid.
        lock_user(db, int(claims["sub"]))
        session = db.get(AuthSession, claims["sid"], populate_existing=True)
        if session and session.user_id_fk == int(claims["sub"]):
            if not bearer:
                check_csrf(request, session)
            session.revoked_at = session.revoked_at or utcnow()
            db.commit()
            break
    clear_auth_cookies(response)
    response.headers["Cache-Control"] = "no-store"
    return {"message": "Logged out"}


@router.post("/change-password")
def change_password(data: UserChangePassword, request: Request, response: Response,
                    db: Session = Depends(get_db),
                    csrf_token: str | None = Header(default=None, alias="X-CSRF-Token")):
    context = authenticate(request, db)
    user = lock_user(db, context.user.id)
    check_user(user)
    # Revalidate after locking, so a concurrent logout/password change wins safely.
    active_session(db, {"sid": context.session.id, "sub": str(user.id)})
    if not user.verify_password(data.old_password):
        raise HTTPException(400, "Current password is incorrect")
    if user.verify_password(data.new_password):
        raise HTTPException(400, "New password must differ from the current password")
    user.set_password(data.new_password)
    for session in db.query(AuthSession).filter(
            AuthSession.user_id_fk == user.id, AuthSession.revoked_at.is_(None)):
        session.revoked_at = utcnow()
    db.commit()
    clear_auth_cookies(response)
    response.headers["Cache-Control"] = "no-store"
    return {"message": "Password changed; please log in again"}
