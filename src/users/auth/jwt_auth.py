from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from fastapi import Response
from core import setting


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def aware(value: datetime) -> datetime:
    # SQLite returns naive timestamps; PostgreSQL columns use UTC offsets.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def create_token(user_id: int, session_id: str, kind: str, expires_at: datetime,
                 token_id: str | None = None) -> str:
    key = setting.SECRET_KEY if kind == "access" else setting.REFRESH_TOKEN_SECRET_KEY
    return jwt.encode({
        "sub": str(user_id), "sid": session_id, "jti": token_id or str(uuid4()),
        "token_type": kind, "iat": utcnow(), "exp": expires_at,
    }, key, algorithm=setting.ALGORITHM)


def create_access_token(user_id: int, session_id: str, expires_at: datetime) -> str:
    expiry = min(aware(expires_at), utcnow() + timedelta(minutes=setting.ACCESS_TOKEN_EXPIRE_MINUTES))
    return create_token(user_id, session_id, "access", expiry)


def create_refresh_token(user_id: int, session_id: str, expires_at: datetime,
                         token_id: str | None = None) -> str:
    return create_token(user_id, session_id, "refresh", expires_at, token_id)


def decode_claims(token: str, kind: str = "access") -> dict:
    key = setting.SECRET_KEY if kind == "access" else setting.REFRESH_TOKEN_SECRET_KEY
    payload = jwt.decode(token, key, algorithms=[setting.ALGORITHM], options={
        "require": ["sub", "sid", "jti", "token_type", "iat", "exp"],
    })
    if payload["token_type"] != kind:
        raise jwt.InvalidTokenError("Wrong token type")
    if not isinstance(payload["sub"], str) or not payload["sub"].isdigit():
        raise jwt.InvalidTokenError("Invalid subject")
    if not isinstance(payload["sid"], str) or not payload["sid"]:
        raise jwt.InvalidTokenError("Invalid session")
    return payload


def decode_token(token: str) -> int:
    return int(decode_claims(token, "access")["sub"])


def set_coookie(token_type: str, my_token: str, response: Response,
                max_age: int | None = None):
    if max_age is None:
        minutes = (setting.REFRESH_TOKEN_EXPIRE_MINUTES if token_type == "refresh_token"
                   else setting.ACCESS_TOKEN_EXPIRE_MINUTES)
        max_age = minutes * 60
    response.set_cookie(token_type, my_token, httponly=token_type != "csrf_token",
                        secure=setting.COOKIE_SECURE, samesite="lax", path="/",
                        max_age=max_age)


def clear_auth_cookies(response: Response):
    for name in ("access_token", "refresh_token", "csrf_token"):
        response.delete_cookie(name, path="/", secure=setting.COOKIE_SECURE,
                               httponly=name != "csrf_token", samesite="lax")


def set_auth_cookies(response: Response, tokens: dict, csrf_token: str | None = None):
    set_coookie("access_token", tokens["access_token"], response, tokens["expires_in"])
    set_coookie("refresh_token", tokens["refresh_token"], response, tokens["refresh_expires_in"])
    if csrf_token is not None:
        set_coookie("csrf_token", csrf_token, response, tokens["refresh_expires_in"])
    response.headers["Cache-Control"] = "no-store"
