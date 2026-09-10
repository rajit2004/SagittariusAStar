
from fastapi import APIRouter, Depends, HTTPException, status
from core.auth import get_current_user
from services.firestore_service import UserService
from services.rate_limit_service import RateLimitService
from services.sms_summary_service import (
    GSM7_SINGLE_SEGMENT,
    build_summary,
    fit_to_budget,
)
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
import os
import re

PHONE_PATTERN = r"^\+[1-9]\d{1,14}$"

SMS_MAX_CHARS = GSM7_SINGLE_SEGMENT

class SMSRequest(BaseModel):

    phone_number: Optional[str] = Field(
        None,
        pattern=PHONE_PATTERN,
        description=(
            "Optional. If given, must match the number saved on your "
            "account — it does not choose where the message goes. Omit it."
        ),
    )
    message: Optional[str] = Field(
        None,
        description=(
            "Ignored. The summary is generated server-side from your own "
            "logged cycle data. Kept only so older clients still validate."
        ),
    )

def registered_phone(user: Optional[Dict[str, Any]]) -> Optional[str]:
    if not user:
        return None
    candidate = (user.get("phone") or user.get("sms_phone_number") or "").strip()
    return candidate or None

_fit_to_one_segment = fit_to_budget

def generate_cycle_sms_summary(user_id: str) -> str:
    from datetime import date

    from services.scoring_service import get_user_scores

    score_data = get_user_scores(user_id)

    return build_summary(
        score_data.get("logs") or [],
        profile=score_data.get("profile"),
        today=date.today(),
    )

class SMSSettings(BaseModel):
    phoneNumber: Optional[str] = ""
    enabled: bool = False

    @property
    def normalized_phone(self) -> Optional[str]:
        return self.phoneNumber.strip() if self.phoneNumber else None

class SMSSettingsResponse(BaseModel):
    phoneNumber: str
    enabled: bool

class SMSSendResponse(BaseModel):
    message: str
    sid: str

router = APIRouter(tags=["SMS"])

sms_history = []

@router.get(
    "/settings",
    response_model=SMSSettingsResponse,
    summary="Get SMS notification settings",
    description="Returns the user's current SMS notification preferences, including the registered phone number and whether SMS summaries are enabled.",
)
async def get_sms_settings(current_user: dict = Depends(get_current_user)):
    user = UserService.get_user_by_id(current_user["id"])
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return {
        "phoneNumber": registered_phone(user) or "",
        "enabled": bool(user.get("sms_enabled", False)),
    }

@router.post(
    "/settings",
    response_model=SMSSettingsResponse,
    summary="Save SMS notification settings",
    description="Updates the user's SMS notification preferences. A phone number is required when enabling SMS summaries, and must be in E.164 format.",
)
async def save_sms_settings(
    settings: SMSSettings,
    current_user: dict = Depends(get_current_user),
):
    phone = settings.normalized_phone
    if settings.enabled and not phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A phone number is required to enable SMS summaries.",
        )
    if phone and not re.match(PHONE_PATTERN, phone):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number must be in E.164 format, e.g. +919876543210.",
        )

    UserService.update_user(
        current_user["id"],
        {
            "phone": phone or "",
            "sms_phone_number": phone or "",
            "sms_enabled": settings.enabled,
        },
    )
    return {"phoneNumber": phone or "", "enabled": settings.enabled}

@router.post(
    "/send-summary",
    response_model=SMSSendResponse,
    summary="Send SMS summary",
    description=(
        "Sends your cycle summary by SMS **to the number saved on your own "
        "account**. Rate-limited to one message per 60 seconds per user.\n\n"
        "The destination is not a request parameter. `phone_number` is "
        "optional and, when present, must match the number already on the "
        "account — supplying a different one is a `403`, not a redirect. "
        "`message` is ignored: the body is generated server-side from your "
        "logged cycle data.\n\n"
        "Both fields are retained only so clients written against the "
        "previous contract still validate. New client work should send an "
        "empty body.\n\n"
        "Returns `409` when no number is saved yet — save one through "
        "`POST /sms/settings` first."
    ),
)
async def send_sms_summary(
    request: SMSRequest,
    current_user: dict = Depends(get_current_user)
):
    user_id = current_user["id"]

    user = UserService.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    destination = registered_phone(user)
    if not destination:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "No phone number is saved on this account. "
                "Save one in SMS settings before sending a summary."
            ),
        )

    if not re.match(PHONE_PATTERN, destination):

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The phone number saved on this account is not in E.164 "
                "format. Please save it again in SMS settings."
            ),
        )

    if request.phone_number and request.phone_number != destination:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Summaries are only sent to the phone number saved on your "
                "own account."
            ),
        )

    remaining = RateLimitService.is_rate_limited(
        key=f"sms:{user_id}",
        limit=1,
        window_seconds=60,
    )

    if remaining is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please wait 60 seconds before sending another SMS.",
            headers={"Retry-After": str(int(remaining))},
        )

    body_text = generate_cycle_sms_summary(user_id)

    try:
        from twilio.rest import Client
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Twilio is not installed. Please install it with `pip install twilio`."
        )

    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_phone = os.getenv("TWILIO_PHONE_NUMBER")

    if not account_sid or not auth_token or not from_phone:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Twilio credentials are not configured. Please set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER in .env."
        )

    try:
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            body=body_text,
            from_=from_phone,
            to=destination,
        )
        return {"message": "SMS sent successfully", "sid": message.sid}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send SMS: {str(e)}"
        )
