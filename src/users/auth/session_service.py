from dataclasses import dataclass
from datetime import timedelta
from hashlib import sha256
from hmac import compare_digest
from secrets import token_urlsafe
from uuid import uuid4

import jwt
from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, lazyload

from core import setting
from ..models import AuthSession, RefreshCredential, UserModel
from .jwt_auth import aware, utcnow, decode_claims, create_access_token, create_refresh_token


def digest(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def check_origin(request: Request):
    origin = request.headers.get("origin")
    allowed = {str(request.base_url).rstrip("/"), *setting.AUTH_ALLOWED_ORIGINS}
    if origin and origin.rstrip("/") not in allowed:
        raise HTTPException(403, "Untrusted request origin")
    if request.headers.get("sec-fetch-site") == "cross-site" and not origin:
        raise HTTPException(403, "Cross-site request rejected")


def check_csrf(request: Request, session: AuthSession):
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    check_origin(request)
    value = request.headers.get("x-csrf-token", "")
    if not value or not compare_digest(digest(value), session.csrf_hash):
        raise HTTPException(403, "Missing or invalid X-CSRF-Token")


def lock_user(db: Session, user_id: int) -> UserModel:
    # All session mutations lock this row first, including the first login.
    user = db.execute(select(UserModel).options(lazyload(UserModel.profile))
                      .where(UserModel.id == user_id).with_for_update(of=UserModel)
                      .execution_options(populate_existing=True)).scalar_one_or_none()
    if user is None:
        raise HTTPException(401, "Invalid credentials")
    return user


def check_user(user: UserModel):
    if not user.is_active or user.is_delete:
        raise HTTPException(403, "Account is inactive or deleted")


def claims_or_401(token: str, kind: str) -> dict:
    try:
        return decode_claims(token, kind)
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise HTTPException(401, "Invalid or expired token") from None


def active_session(db: Session, claims: dict) -> AuthSession:
    session = db.get(AuthSession, claims["sid"], populate_existing=True)
    if (session is None or session.user_id_fk != int(claims["sub"])
            or session.revoked_at is not None or aware(session.expires_at) <= utcnow()):
        raise HTTPException(401, "Session is expired or revoked")
    return session


@dataclass
class AuthContext:
    user: UserModel
    session: AuthSession


def authenticate(request: Request, db: Session) -> AuthContext:
    authorization = request.headers.get("authorization", "")
    bearer = authorization.lower().startswith("bearer ")
    token = authorization[7:].strip() if bearer else request.cookies.get("access_token")
    if not token:
        raise HTTPException(401, "Please log in")
    claims = claims_or_401(token, "access")
    session = active_session(db, claims)
    user = db.get(UserModel, int(claims["sub"]))
    if user is None:
        raise HTTPException(401, "Invalid credentials")
    check_user(user)
    if not bearer:
        check_csrf(request, session)
    return AuthContext(user, session)


def issue_pair(db: Session, user: UserModel, session: AuthSession) -> tuple[dict, str]:
    now = utcnow()
    token_id = str(uuid4())
    refresh = create_refresh_token(user.id, session.id, aware(session.expires_at), token_id)
    access = create_access_token(user.id, session.id, aware(session.expires_at))
    db.add(RefreshCredential(id=token_id, session_id=session.id, token_hash=digest(refresh),
                            created_at=now, expires_at=session.expires_at))
    remaining = max(0, int((aware(session.expires_at) - now).total_seconds()))
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer",
            "expires_in": min(setting.ACCESS_TOKEN_EXPIRE_MINUTES * 60, remaining),
            "refresh_expires_in": remaining}, token_id


def start_session(db: Session, user: UserModel, password: str) -> tuple[dict, str]:
    user = lock_user(db, user.id)
    # Re-check after acquiring the lock: the password might have changed meanwhile.
    if not user.verify_password(password):
        raise HTTPException(401, "Invalid username or password")
    check_user(user)
    now = utcnow()
    previous = db.scalars(select(AuthSession).where(
        AuthSession.user_id_fk == user.id, AuthSession.revoked_at.is_(None))).all()
    for session in previous:
        if aware(session.expires_at) > now:
            raise HTTPException(409, "An active session already exists; log out first")
        session.revoked_at = now
    db.flush()
    csrf = token_urlsafe(32)
    session = AuthSession(id=str(uuid4()), user_id_fk=user.id, created_at=now,
                          expires_at=now + timedelta(minutes=setting.REFRESH_TOKEN_EXPIRE_MINUTES),
                          csrf_hash=digest(csrf))
    db.add(session)
    db.flush()
    user.last_login = now
    tokens, _ = issue_pair(db, user, session)
    return tokens, csrf


def rotate_refresh(db: Session, token: str, request: Request, from_cookie: bool) -> dict:
    claims = claims_or_401(token, "refresh")
    user = lock_user(db, int(claims["sub"]))
    check_user(user)
    session = active_session(db, claims)
    if from_cookie:
        check_csrf(request, session)
    credential = db.get(RefreshCredential, claims["jti"], populate_existing=True)
    if (credential is None or credential.session_id != session.id
            or not compare_digest(credential.token_hash, digest(token))
            or aware(credential.expires_at) <= utcnow()):
        raise HTTPException(401, "Invalid refresh token")
    if credential.consumed_at is not None:
        # Retain the history and revoke the whole session on replay.
        session.revoked_at = utcnow()
        db.commit()
        raise HTTPException(401, "Refresh token reused; session revoked")
    credential.consumed_at = utcnow()
    tokens, new_id = issue_pair(db, user, session)
    credential.replaced_by_id = new_id
    return tokens
