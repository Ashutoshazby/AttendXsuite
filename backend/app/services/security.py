from datetime import timedelta
from jose import jwt
from passlib.context import CryptContext
from ..config import get_settings
from ..utils.timezone import now_utc

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_token(payload: dict) -> str:
    settings = get_settings()
    expires = now_utc() + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode({**payload, "exp": expires}, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> dict:
    return jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
