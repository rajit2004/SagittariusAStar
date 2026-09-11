from fastapi import APIRouter, HTTPException, status, Depends, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List
from core.auth import (
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
    revoke_refresh_token,
    revoke_all_user_refresh_tokens,
    generate_reset_token,
    verify_reset_token,
    generate_verification_token,
    verify_email_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    OTP_SESSION_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    COOKIE_NAME,
    REFRESH_COOKIE_NAME,
    get_current_user,
    get_password_hash,
    verify_password,
)
from core.email_identity import normalize_email
from core.password_policy import enforce_password_policy, requirements as password_requirements
from core.rate_limits import (
    EMAIL_VERIFY_IP,
    FIREBASE_LOGIN_IP,
    LOGIN_ACCOUNT,
    LOGIN_IP,
    PASSWORD_RESET_CONFIRM_IP,
    PASSWORD_RESET_REQUEST_ACCOUNT,
    PASSWORD_RESET_REQUEST_IP,
    REGISTER_IP,
    TOKEN_REFRESH_IP,
    VERIFICATION_RESEND_ACCOUNT,
    clear as clear_rate_limit,
    client_ip,
    enforce as enforce_rate_limit,
)
from models.user import UserCreate, UserResponse, UserProfileUpdate, UserProfileResponse
from services.firestore_service import UserService

import os
import logging
from pydantic import BaseModel, EmailStr
import firebase_admin.auth

logger = logging.getLogger(__name__)

class FirebaseLoginRequest(BaseModel):
    id_token: str
    fcm_token: Optional[str] = None

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    username: Optional[str] = None
    full_name: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    token: str
    new_password: str

class VerifyEmailRequest(BaseModel):
    email: EmailStr
    token: str

router = APIRouter(tags=["Authentication"])

COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"

COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax").lower()
COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN", None)

def get_client_ip(request: Request) -> str:
    return client_ip(request)

def _set_auth_cookie(response: Response, token: str, max_age_seconds: int | None = None):
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=max_age_seconds or (ACCESS_TOKEN_EXPIRE_MINUTES * 60),
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        domain=COOKIE_DOMAIN,
        path="/",
    )

def _set_refresh_cookie(response: Response, token: str):
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        domain=COOKIE_DOMAIN,
        path="/",
    )

__all__ = ["router", "normalize_email", "get_client_ip"]

@router.post("/firebase-login")
async def firebase_login(request: Request, response: Response, data: FirebaseLoginRequest):

    enforce_rate_limit(FIREBASE_LOGIN_IP, get_client_ip(request))

    try:

        decoded_token = firebase_admin.auth.verify_id_token(data.id_token)

    except firebase_admin.auth.InvalidIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Firebase ID token"
        )
    except Exception as e:
        logger.error(f"Error verifying Firebase ID token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

    phone_number = decoded_token.get('phone_number')

    if not phone_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No phone number found in Firebase token"
        )

    try:

        is_new_user = False
        user = UserService.get_user_by_phone(phone_number)
        if not user:
            is_new_user = True

            user_data = {
                "phone": phone_number,
            }
            user_id = UserService.create_user(user_data)
            user = UserService.get_user_by_id(user_id)

        access_token_expires = timedelta(minutes=OTP_SESSION_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user["id"]}, expires_delta=access_token_expires
        )

        _set_auth_cookie(response, access_token)

        refresh_token = create_refresh_token(user["id"])
        response.set_cookie(
            key=REFRESH_COOKIE_NAME,
            value=refresh_token,
            max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
            httponly=True,
            secure=COOKIE_SECURE,
            samesite=COOKIE_SAMESITE,
            domain=COOKIE_DOMAIN,
            path="/",
        )

        if request.headers.get("X-Client-Platform") == "web":
            return {"token_type": "bearer", "is_new_user": is_new_user}

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "is_new_user": is_new_user
        }
    except Exception as e:
        logger.error(f"Error during firebase login for phone {phone_number}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/logout")
async def logout(response: Response):
    for cookie_name in (COOKIE_NAME, REFRESH_COOKIE_NAME):
        response.delete_cookie(
            key=cookie_name,
            path="/",
            domain=COOKIE_DOMAIN,
        )
    return {"message": "Successfully logged out."}

@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return current_user

@router.get("/profile", response_model=UserProfileResponse)
async def get_profile(current_user: dict = Depends(get_current_user)):
    user = UserService.get_user_by_id(current_user["id"])
    if not user:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    user.pop("password", None)
    return user

@router.patch("/profile", response_model=UserProfileResponse)
async def update_profile(
    profile_data: UserProfileUpdate,
    current_user: dict = Depends(get_current_user),
):
    updates = {k: v for k, v in profile_data.model_dump().items() if v is not None}
    if updates:
        UserService.update_user(current_user["id"], updates)
    user = UserService.get_user_by_id(current_user["id"])
    if not user:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    user.pop("password", None)
    return user

@router.get("/settings", summary="Get per-user app settings")
async def get_settings(current_user: dict = Depends(get_current_user)):
    user = UserService.get_user_by_id(current_user["id"])
    if not user:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return {"settings": user.get("settings", {})}

@router.put("/settings", summary="Save per-user app settings")
async def save_settings(
    settings: dict,
    current_user: dict = Depends(get_current_user),
):
    allowed_keys = {"primary_color", "dark_mode", "language", "cloud_sync", "sms_enabled", "biometric_enabled"}
    filtered = {k: v for k, v in settings.items() if k in allowed_keys and v is not None}
    UserService.update_user(current_user["id"], {"settings": filtered})
    return {"settings": filtered}

@router.delete("/me")
async def delete_me(response: Response, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    deleted_counts = UserService.delete_user(user_id)
    revoke_all_user_refresh_tokens(user_id)

    for cookie_name in (COOKIE_NAME, REFRESH_COOKIE_NAME):
        response.delete_cookie(key=cookie_name, path="/", domain=COOKIE_DOMAIN)

    return {
        "status": "success",
        "detail": "Account deleted successfully",
        "deletedCounts": deleted_counts or {},
    }

@router.get(
    "/password-requirements",
    summary="The password rules this server enforces",
    description=(
        "Returns the minimum length, the byte ceiling, and a plain-language "
        "list of the rules applied to new passwords by `POST /auth/register` "
        "and `POST /auth/reset-password`.\n\n"
        "Exists so a sign-up form can show a user the rules *before* she "
        "submits, without each client keeping its own copy that drifts from "
        "what the server actually enforces. Unauthenticated: the rules are "
        "not a secret, and they are needed on the registration screen."
    ),
)
async def get_password_requirements():
    return password_requirements()

@router.post("/register")
async def register(data: RegisterRequest, request: Request):

    enforce_rate_limit(REGISTER_IP, get_client_ip(request))

    email = normalize_email(data.email)

    enforce_password_policy(
        data.password,
        email=email,
        username=data.username,
    )

    user = UserService.get_user_by_email(data.email)
    if user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists"
        )

    password_hash = get_password_hash(data.password)
    user_data = {
        "email": email,
        "password": password_hash,
        "email_verified": False,
    }
    if data.username:
        user_data["username"] = data.username
    if data.full_name:
        user_data["full_name"] = data.full_name

    try:
        user_id = UserService.create_user(user_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

    verification_token = generate_verification_token(email)
    logger.info(f"Email verification token for {email}: {verification_token}")

    return {
        "id": user_id,
        "email": email,
        "email_verified": False,
        "message": "Registration successful. Please verify your email."
    }

@router.post("/login")
async def login(data: LoginRequest, request: Request, response: Response):

    email = normalize_email(data.email)

    enforce_rate_limit(LOGIN_IP, get_client_ip(request))
    enforce_rate_limit(LOGIN_ACCOUNT, email)

    user = UserService.get_user_by_email(data.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    stored_hash = user.get("password")
    if not stored_hash or not verify_password(data.password, stored_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    clear_rate_limit(LOGIN_ACCOUNT, email)

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["id"]}, expires_delta=access_token_expires
    )
    refresh_token = create_refresh_token(user["id"])

    _set_auth_cookie(response, access_token)
    _set_refresh_cookie(response, refresh_token)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "email_verified": user.get("email_verified", False),
        "user_id": user["id"],
    }

@router.post("/refresh")
async def refresh_token(request: Request, response: Response, data: RefreshTokenRequest | None = None):

    enforce_rate_limit(TOKEN_REFRESH_IP, get_client_ip(request))

    refresh_token_value = None
    if data and data.refresh_token:
        refresh_token_value = data.refresh_token
    else:
        refresh_token_value = request.cookies.get(REFRESH_COOKIE_NAME)

    if not refresh_token_value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token provided"
        )

    user_id = verify_refresh_token(refresh_token_value)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    revoke_refresh_token(refresh_token_value)

    new_access_token = create_access_token(
        data={"sub": user_id},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    new_refresh_token = create_refresh_token(user_id)

    _set_auth_cookie(response, new_access_token)

    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=new_refresh_token,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        domain=COOKIE_DOMAIN,
        path="/",
    )

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }

@router.post("/logout-all")
async def logout_all(current_user: dict = Depends(get_current_user)):
    revoke_all_user_refresh_tokens(current_user["id"])
    return {"message": "All sessions logged out successfully."}

@router.post("/forgot-password")
async def forgot_password(data: ForgotPasswordRequest, request: Request):

    email = normalize_email(data.email)

    enforce_rate_limit(PASSWORD_RESET_REQUEST_IP, get_client_ip(request))
    enforce_rate_limit(PASSWORD_RESET_REQUEST_ACCOUNT, email)

    user = UserService.get_user_by_email(data.email)
    if not user:
        return {"message": "If an account with that email exists, a reset link has been sent."}

    reset_token = generate_reset_token(email)
    logger.info(f"Password reset token for {email}: {reset_token}")

    return {"message": "If an account with that email exists, a reset link has been sent."}

@router.post("/reset-password")
async def reset_password(data: ResetPasswordRequest, request: Request):

    enforce_rate_limit(PASSWORD_RESET_CONFIRM_IP, get_client_ip(request))

    email = normalize_email(data.email)

    if not verify_reset_token(email, data.token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )

    user = UserService.get_user_by_email(data.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    enforce_password_policy(
        data.new_password,
        email=email,
        username=user.get("username"),
    )

    new_hash = get_password_hash(data.new_password)
    UserService.update_user(user["id"], {"password": new_hash})

    revoke_all_user_refresh_tokens(user["id"])

    return {"message": "Password has been reset successfully."}

@router.post("/verify-email")
async def verify_email(data: VerifyEmailRequest, request: Request):
    enforce_rate_limit(EMAIL_VERIFY_IP, get_client_ip(request))

    email = normalize_email(data.email)

    if not verify_email_token(email, data.token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token"
        )

    user = UserService.get_user_by_email(data.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    UserService.update_user(user["id"], {"email_verified": True})
    return {"message": "Email verified successfully."}

@router.post("/resend-verification")
async def resend_verification(data: ForgotPasswordRequest, request: Request):

    email = normalize_email(data.email)

    enforce_rate_limit(EMAIL_VERIFY_IP, get_client_ip(request))
    enforce_rate_limit(VERIFICATION_RESEND_ACCOUNT, email)

    user = UserService.get_user_by_email(data.email)
    if not user:
        return {"message": "If an account with that email exists, a verification email has been sent."}

    if user.get("email_verified"):
        return {"message": "Email is already verified."}

    new_token = generate_verification_token(email)
    logger.info(f"New verification token for {email}: {new_token}")

    return {"message": "If an account with that email exists, a verification email has been sent."}
