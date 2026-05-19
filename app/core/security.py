from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from passlib.exc import UnknownHashError
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except UnknownHashError:
        return False

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return encoded_jwt

def create_password_reset_token(email: str, expires_delta: Optional[timedelta] = None) -> str:
    token_expiry = expires_delta or timedelta(minutes=settings.reset_token_expire_minutes)
    return create_access_token(
        data={"sub": email, "type": "password_reset"},
        expires_delta=token_expiry,
    )

def decode_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None

def verify_token(token: str) -> Optional[str]:
    payload = decode_token(token)
    if payload is None:
        return None
    email: str = payload.get("sub")
    if email is None:
        return None
    return email

def verify_password_reset_token(token: str) -> Optional[str]:
    payload = decode_token(token)
    if payload is None:
        return None
    if payload.get("type") != "password_reset":
        return None
    email: str = payload.get("sub")
    if email is None:
        return None
    return email
