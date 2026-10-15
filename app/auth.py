import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from .database import get_db
from .models import User


def secret():
    value = os.getenv("JWT_SECRET", "")
    if len(value) < 32:
        raise RuntimeError("Set JWT_SECRET to at least 32 random characters")
    return value


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
    return salt + ":" + digest


def verify(password, stored):
    salt, digest = stored.split(":")
    actual = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
    return hmac.compare_digest(digest, actual)


def token(user):
    return jwt.encode(
        {"sub": user.username, "exp": datetime.now(timezone.utc) + timedelta(hours=2)},
        secret(),
        algorithm="HS256",
    )


def current(request: Request, db=Depends(get_db)):
    raw = request.headers.get("Authorization", "").removeprefix("Bearer ")
    try:
        claims = jwt.decode(raw, secret(), algorithms=["HS256"])
        user = db.scalar(select(User).where(User.username == claims["sub"]))
        if not user:
            raise ValueError()
        return user
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(401, "Please sign in")


def roles(*allowed):
    def check(user=Depends(current)):
        if user.role not in allowed:
            raise HTTPException(403, "Your role cannot perform this action")
        return user

    return check
