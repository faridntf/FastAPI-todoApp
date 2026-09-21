
from datetime import datetime, timedelta, timezone
from fastapi import Response
from core import setting
import jwt



def create_access_token(user_id: int) -> str:
    isuueTime = datetime.now(timezone.utc)
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=setting.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": str(user_id),
        "iat" : isuueTime,
        "exp": expire,
    }
    token = jwt.encode(
        payload,
        setting.SECRET_KEY,
        algorithm=setting.ALGORITHM,
    )
    return token

def create_refresh_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=setting.REFRESH_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": str(user_id),
        "isuTime" : datetime.now(timezone.utc),
        "exp": expire,
    }
    token = jwt.encode(
        payload,
        setting.SECRET_KEY,
        algorithm=[setting.ALGORITHM],
    )
    return token

def decode_token(token: str) -> int:
    payload = jwt.decode(
        token,
        setting.SECRET_KEY,
        algorithms=[setting.ALGORITHM],
    )
    user_id = payload.get("sub")
    if user_id is None:
        raise ValueError("Token subject missing")
    return int(user_id)

def set_coookie(token_type:str, my_token: str, response: Response):
    response.set_cookie(
        key=token_type,
        value=my_token,
        httponly=True,
        secure=False, #todo => to production hatmn avaz beshe
        samesite="lax",
        max_age= setting.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/"
    )
    return "ok"
