import bcrypt
import secrets
import hashlib
from jose import JWTError, jwt
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import OAuth2PasswordBearer
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
from core.email_identity import normalize_email
from services import token_store
from services.firestore_service import UserService

SECRET_KEY = os.getenv("JWT_SECRET")
if not SECRET_KEY:
    raise ValueError("JWT_SECRET must be set in environment variables. Generate one using `python -c 'import secrets; print(secrets.token_urlsafe(32))'` and add it to .env")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
OTP_SESSION_EXPIRE_MINUTES = 5256000
REFRESH_TOKEN_EXPIRE_DAYS = 7
RESET_TOKEN_EXPIRE_MINUTES = 15
VERIFY_TOKEN_EXPIRE_HOURS = 24

COOKIE_NAME = "rhythma_access_token"
REFRESH_COOKIE_NAME = "rhythma_refresh_token"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/firebase-login", auto_error=False)

refresh_token_store = token_store.TokenNamespace(token_store.KIND_REFRESH)
reset_token_store = token_store.TokenNamespace(token_store.KIND_PASSWORD_RESET)
verification_token_store = token_store.TokenNamespace(
    token_store.KIND_EMAIL_VERIFICATION
)

def _email_key(email: str) -> str:
    return normalize_email(email)

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def _parse_dt(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None

def cleanup_expired_refresh_tokens():
    now = datetime.now(timezone.utc)
    expired = []
    for k, v in refresh_token_store.items():
        expires_at = _parse_dt(v.get("expires_at"))
        if expires_at is not None and now > expires_at:
            expired.append(k)
    for k in expired:
        refresh_token_store.pop(k, None)

def create_refresh_token(user_id: str) -> str:
    cleanup_expired_refresh_tokens()
    token = secrets.token_urlsafe(48)
    token_store.put(
        token_store.KIND_REFRESH,
        token,
        {"user_id": user_id},
        timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )
    return token

def verify_refresh_token(token: str) -> Optional[str]:
    entry = token_store.get(token_store.KIND_REFRESH, token)
    if not entry:
        return None
    return entry.get("user_id")

def revoke_refresh_token(token: str):
    token_store.delete(token_store.KIND_REFRESH, token)

def revoke_all_user_refresh_tokens(user_id: str):
    token_store.delete_for_user(token_store.KIND_REFRESH, user_id)

def generate_reset_token(email: str) -> str:
    token = secrets.token_urlsafe(32)

    token_store.put(
        token_store.KIND_PASSWORD_RESET,
        _email_key(email),
        {"token_hash": _hash_token(token)},
        timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES),
    )
    return token

def verify_reset_token(email: str, token: str) -> bool:
    key = _email_key(email)
    entry = token_store.get(token_store.KIND_PASSWORD_RESET, key)
    if not entry:
        return False
    if not secrets.compare_digest(entry.get("token_hash", ""), _hash_token(token)):

        return False
    token_store.delete(token_store.KIND_PASSWORD_RESET, key)
    return True

def generate_verification_token(email: str) -> str:
    token = secrets.token_urlsafe(32)
    token_store.put(
        token_store.KIND_EMAIL_VERIFICATION,
        _email_key(email),
        {"token_hash": _hash_token(token)},
        timedelta(hours=VERIFY_TOKEN_EXPIRE_HOURS),
    )
    return token

def verify_email_token(email: str, token: str) -> bool:
    key = _email_key(email)
    entry = token_store.get(token_store.KIND_EMAIL_VERIFICATION, key)
    if not entry:
        return False
    if not secrets.compare_digest(entry.get("token_hash", ""), _hash_token(token)):
        return False
    token_store.delete(token_store.KIND_EMAIL_VERIFICATION, key)
    return True

async def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = UserService.get_user_by_id(user_id)
    if user is None:
        raise credentials_exception
    return {
        "id": user["id"],
        "phone": user.get("phone"),
        "username": user.get("username"),
        "email": user.get("email"),
        "role": user.get("role", "patient"),
    }
