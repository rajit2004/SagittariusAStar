
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, EmailStr, Field

from core import auth_router as auth_router_module
from core.email_identity import normalize_email
from core.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    create_refresh_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from core.password_policy import enforce_password_policy
from core.rate_limits import (
    LOGIN_ACCOUNT,
    LOGIN_IP,
    PROVIDER_REGISTER_IP,
    REGISTER_IP,
    clear as clear_rate_limit,
    enforce as enforce_rate_limit,
)
from services import access_log_service
from services.firestore_service import UserService
from services.provider_service import (
    DEFAULT_CONSENTS_PAGE,
    DEFAULT_PATIENTS_PAGE,
    MAX_CONSENTS_PAGE,
    MAX_PATIENTS_PAGE,
    ConsentService,
    ProviderService,
)

router = APIRouter(tags=["Provider Dashboard"])

MAX_NAME_CHARS = 120
MAX_SPECIALTY_CHARS = 120
MAX_LICENSE_CHARS = 64

class RegisterProviderRequest(BaseModel):
    email: EmailStr

    password: str
    username: Optional[str] = Field(None, max_length=MAX_NAME_CHARS)
    full_name: Optional[str] = Field(None, max_length=MAX_NAME_CHARS)
    specialty: Optional[str] = Field(None, max_length=MAX_SPECIALTY_CHARS)
    license_number: Optional[str] = Field(None, max_length=MAX_LICENSE_CHARS)

class ProviderLoginRequest(BaseModel):
    email: EmailStr
    password: str

class GrantConsentRequest(BaseModel):
    provider_email: EmailStr

def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None

def _require_role(current_user: dict, role: str) -> dict:
    if current_user.get("role", "patient") != role:
        if role == "provider":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="A healthcare provider account is required",
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A patient account is required",
        )
    return current_user

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_provider(data: RegisterProviderRequest, request: Request):
    enforce_rate_limit(REGISTER_IP, auth_router_module.get_client_ip(request))
    enforce_rate_limit(PROVIDER_REGISTER_IP, auth_router_module.get_client_ip(request))

    email = normalize_email(data.email)
    username = _clean(data.username)

    enforce_password_policy(data.password, email=email, username=username)

    existing = UserService.get_user_by_email(data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user_data = {
        "email": email,
        "password": get_password_hash(data.password),
        "email_verified": False,
        "role": "provider",
        "username": username,
        "full_name": _clean(data.full_name),
        "specialty": _clean(data.specialty),
        "license_number": _clean(data.license_number),
    }
    try:
        user_id = UserService.create_user(user_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Provider registration failed",
        ) from e

    return {
        "id": user_id,
        "email": email,
        "role": "provider",
        "message": "Provider account created.",
    }

@router.post("/login")
async def login_provider(
    data: ProviderLoginRequest, request: Request, response: Response
):
    email = normalize_email(data.email)

    enforce_rate_limit(LOGIN_IP, auth_router_module.get_client_ip(request))
    enforce_rate_limit(LOGIN_ACCOUNT, email)

    user = UserService.get_user_by_email(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    stored_hash = user.get("password")
    password_ok = bool(stored_hash) and verify_password(data.password, stored_hash)

    if not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if user.get("role") != "provider":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This is not a healthcare provider account",
        )

    clear_rate_limit(LOGIN_ACCOUNT, email)

    access_token = create_access_token(
        data={"sub": user["id"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token = create_refresh_token(user["id"])

    auth_router_module._set_auth_cookie(response, access_token)
    auth_router_module._set_refresh_cookie(response, refresh_token)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "email_verified": user.get("email_verified", False),
        "user_id": user["id"],
        "role": "provider",
    }

@router.get("/me")
async def provider_me(current_user: dict = Depends(get_current_user)):
    _require_role(current_user, "provider")
    user = UserService.get_user_by_id(current_user["id"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    user.pop("password", None)
    return user

@router.post("/consents", status_code=status.HTTP_201_CREATED)
async def grant_consent(
    data: GrantConsentRequest, current_user: dict = Depends(get_current_user)
):
    _require_role(current_user, "patient")
    return ConsentService.grant(current_user["id"], data.provider_email)

@router.get("/consents")
async def list_consents(
    limit: int = Query(
        DEFAULT_CONSENTS_PAGE,
        ge=1,
        le=MAX_CONSENTS_PAGE,
        description="How many consents to return (1-100).",
    ),
    offset: int = Query(0, ge=0, description="How many consents to skip."),
    current_user: dict = Depends(get_current_user),
):
    _require_role(current_user, "patient")
    consents, has_more = ConsentService.list_page_for_patient(
        current_user["id"], limit=limit, offset=offset
    )
    access = access_log_service.summary_for_patient(current_user["id"])

    for consent in consents:
        stats = access.get(consent.get("provider_id")) or {}
        consent["viewCount"] = stats.get("viewCount", 0)
        consent["lastAccessedAt"] = stats.get("lastAccessedAt")

    return {
        "consents": consents,
        "page": {
            "limit": limit,
            "offset": offset,
            "count": len(consents),
            "hasMore": has_more,
            "nextOffset": offset + len(consents) if has_more else None,
        },
    }

@router.get("/access-log")
async def list_access_log(
    limit: int = Query(
        access_log_service.DEFAULT_ACCESS_LOG_PAGE,
        ge=1,
        le=access_log_service.MAX_ACCESS_LOG_PAGE,
        description="How many entries to return (1-100).",
    ),
    offset: int = Query(0, ge=0, description="How many entries to skip."),
    current_user: dict = Depends(get_current_user),
):
    _require_role(current_user, "patient")
    entries, has_more = access_log_service.list_for_patient(
        current_user["id"], limit=limit, offset=offset
    )

    return {
        "entries": entries,
        "page": {
            "limit": limit,
            "offset": offset,
            "count": len(entries),
            "hasMore": has_more,
            "nextOffset": offset + len(entries) if has_more else None,
        },
    }

@router.delete("/consents/{consent_id}")
async def revoke_consent(
    consent_id: str, current_user: dict = Depends(get_current_user)
):
    _require_role(current_user, "patient")
    return ConsentService.revoke(current_user["id"], consent_id)

@router.get("/patients")
async def list_patients(
    limit: int = Query(
        DEFAULT_PATIENTS_PAGE,
        ge=1,
        le=MAX_PATIENTS_PAGE,
        description="How many patients to return (1-100).",
    ),
    offset: int = Query(0, ge=0, description="How many patients to skip."),
    current_user: dict = Depends(get_current_user),
):
    _require_role(current_user, "provider")
    patients, has_more = ProviderService.patient_summaries_page(
        current_user["id"], limit=limit, offset=offset
    )
    return {
        "patients": patients,
        "page": {
            "limit": limit,
            "offset": offset,
            "count": len(patients),
            "hasMore": has_more,
            "nextOffset": offset + len(patients) if has_more else None,
        },
    }

@router.get("/patients/{patient_id}")
async def patient_detail(
    patient_id: str, current_user: dict = Depends(get_current_user)
):
    _require_role(current_user, "provider")
    return ProviderService.patient_detail(current_user["id"], patient_id)
