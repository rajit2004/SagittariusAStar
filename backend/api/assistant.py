import logging
import os
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import List, Literal, Optional

import google.generativeai as genai
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from core.auth import get_current_user
from core.model_response import ANSWER_STATUSES, interpret
from services.firestore_service import AssistantConversationService
from services.medical_knowledge_service import MedicalKnowledgeService
from services.rate_limit_service import RateLimitService

logger = logging.getLogger(__name__)

_assistant_rate_history: dict = {}

def is_rate_limited(user_id: str) -> Optional[int]:
    return RateLimitService.is_rate_limited(
        key=f"assistant:{user_id}",
        limit=ASSISTANT_RATE_LIMIT,
        window_seconds=ASSISTANT_RATE_WINDOW,
    )

medical_knowledge_service = MedicalKnowledgeService()

ASSISTANT_RATE_LIMIT = int(os.getenv("ASSISTANT_RATE_LIMIT", "10"))
ASSISTANT_RATE_WINDOW = int(os.getenv("ASSISTANT_RATE_WINDOW", "60"))

SUPPORTED_LANGUAGES = [
    {"code": "en", "name": "English"},
    {"code": "hi", "name": "Hindi"},
    {"code": "mr", "name": "Marathi"},
    {"code": "ta", "name": "Tamil"},
    {"code": "te", "name": "Telugu"},
    {"code": "kn", "name": "Kannada"},
    {"code": "ml", "name": "Malayalam"},
    {"code": "gu", "name": "Gujarati"},
]

SUPPORTED_LANGUAGE_CODES = frozenset(lang["code"] for lang in SUPPORTED_LANGUAGES)

ASSISTANT_MAX_MESSAGE_CHARS = int(os.getenv("ASSISTANT_MAX_MESSAGE_CHARS", "2000"))
ASSISTANT_MAX_HISTORY_MESSAGES = int(os.getenv("ASSISTANT_MAX_HISTORY_MESSAGES", "20"))
ASSISTANT_MAX_HISTORY_CHARS = int(os.getenv("ASSISTANT_MAX_HISTORY_CHARS", "2000"))

ASSISTANT_MAX_OUTPUT_TOKENS = int(os.getenv("ASSISTANT_MAX_OUTPUT_TOKENS", "1024"))

def to_single_line(value: str) -> str:

    flattened = "".join(
        " "
        if char in ("\u2028", "\u2029") or unicodedata.category(char) == "Cc"
        else char
        for char in value
    )
    return re.sub(r"\s+", " ", flattened).strip()

class ChatMessage(BaseModel):

    role: Literal["user", "model"]
    content: str = Field(
        ...,
        min_length=1,
        max_length=ASSISTANT_MAX_HISTORY_CHARS,
        description="One turn of the conversation.",
    )

class AssistantRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=ASSISTANT_MAX_MESSAGE_CHARS,
        description="The user's question. Length-capped before any model call is made.",
    )
    language: Optional[str] = Field(
        "en",
        description=(
            "One of the codes from GET /assistant/languages. Rejected with "
            "422 if it is anything else."
        ),
    )
    history: Optional[List[ChatMessage]] = Field(
        None,
        max_length=ASSISTANT_MAX_HISTORY_MESSAGES,
        description=(
            "Recent turns, used only when nothing is persisted server-side "
            "for this user."
        ),
    )

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message cannot be empty.")
        return value

    @field_validator("language")
    @classmethod
    def language_must_be_supported(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return "en"

        normalized = value.strip().lower().replace("_", "-").split("-")[0]

        if normalized not in SUPPORTED_LANGUAGE_CODES:
            supported = ", ".join(sorted(SUPPORTED_LANGUAGE_CODES))
            raise ValueError(
                f"Unsupported language {value!r}. Supported languages: {supported}."
            )
        return normalized

class AssistantSource(BaseModel):

    name: str
    title: str
    url: str
    accessedOn: str

class AssistantResponse(BaseModel):
    response: str
    language: str
    disclaimer: str = "Please consult a healthcare professional for medical advice."

    sources: List[AssistantSource] = Field(default_factory=list)

    wasShortened: bool = False

SYSTEM_PROMPT = """
You are Rhythma, a compassionate and knowledgeable AI menstrual health companion designed specifically for women in India. Your purpose is to provide supportive, culturally sensitive, and medically responsible guidance on menstrual health, reproductive health, emotional well-being, and overall women's health.

You ARE able to discuss and explain reproductive health topics including ovulation, menstrual cycles, fertility, PMS, endometriosis, contraception, menopause, and general women's health. These are core topics you should help with confidently.

Key guidelines:
- Always prioritize safety and remind users to consult a doctor for medical advice.
- Keep responses concise, empathetic, and easy to understand.
- Use simple English or the user's preferred Indian language.
- Be non-judgmental and encouraging.
- Do not provide medical diagnoses - encourage professional consultation.
- Never prescribe medication.
- Answer health questions helpfully using your knowledge and any provided references.
- Always end responses that involve symptoms or health concerns with a gentle reminder to consult a healthcare professional.

"""

router = APIRouter(tags=["AI Assistant"])

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY is not set. Assistant requests will fail until it is configured.")
else:
    genai.configure(api_key=GEMINI_API_KEY)


@router.post(
    "/chat",
    response_model=AssistantResponse,
    summary="Ask the AI health assistant a question",
    description=(
        "Answers a question about menstrual and reproductive health, "
        "grounded in the curated medical reference dataset and in the "
        "user's recent conversation.\n\n"
        "Input is bounded: `message` and each `history[].content` are "
        "length-capped, `history` is item-capped, `role` accepts only "
        "`user` or `model`, and `language` must be one of the codes from "
        "`GET /assistant/languages`. All of it is enforced by the request "
        "model, so an over-limit or malformed request returns `422` "
        "without a model call being made.\n\n"
        "Returns `429` with `Retry-After` when the per-user rate limit is "
        "exceeded."
    ),
)
async def chat(
    request: AssistantRequest,
    current_user: dict = Depends(get_current_user),
):
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="AI service not configured.")

    user_id = current_user.get("id")

    remaining = RateLimitService.is_rate_limited(
        key=f"assistant:{user_id}",
        limit=ASSISTANT_RATE_LIMIT,
        window_seconds=ASSISTANT_RATE_WINDOW,
    )
    if remaining is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Please wait {remaining} seconds before sending another message.",
            headers={"Retry-After": str(remaining)},
        )

    persisted = AssistantConversationService.get_recent_messages(user_id, limit=10)
    history = [ChatMessage(**m) if isinstance(m, dict) else m for m in persisted]

    if not history and request.history:
        history = request.history[-10:]

    retrieval_query = " ".join(
        [m.content for m in history[-5:] if m.role == "user" and m.content]
        + [request.message]
    ).strip()
    references = medical_knowledge_service.retrieve(retrieval_query, limit=3)
    grounding = medical_knowledge_service.build_grounding_block(references)

    prompt_parts = [
        f"System: {SYSTEM_PROMPT}",
    ]

    if grounding:
        prompt_parts.append(f"Grounding: {grounding}")

    prompt_parts.append(f"Language: Respond in {to_single_line(request.language or 'en')}.")

    prompt_parts.append("\n--- Conversation History ---")

    if history:
        for msg in history[-10:]:
            if msg.role == "user":
                prompt_parts.append(f"User: {msg.content}")
            elif msg.role == "model":
                prompt_parts.append(f"Assistant: {msg.content}")
    else:
        prompt_parts.append("(No previous messages)")

    prompt_parts.extend(
        [
            "\n--- Current Message ---",
            f"User: {request.message}",
            "Assistant:",
        ]
    )

    try:
        model = genai.GenerativeModel("models/gemini-2.5-flash")
        response = model.generate_content(
            "\n".join(prompt_parts),
            generation_config={"max_output_tokens": ASSISTANT_MAX_OUTPUT_TOKENS},
        )

        outcome = interpret(response)

        if outcome.status not in ANSWER_STATUSES:
            logger.warning(
                "The assistant returned no usable answer (status=%s, finish_reason=%s)",
                outcome.status,
                outcome.finish_reason,
                extra={
                    "assistant_status": outcome.status,
                    "assistant_finish_reason": outcome.finish_reason,
                },
            )

        reply = outcome.text

        AssistantConversationService.add_messages(user_id, [
            {"role": "user", "content": request.message},
            {"role": "model", "content": reply},
        ])

        return AssistantResponse(
            response=reply,
            language=request.language or "en",
            disclaimer="Please consult a healthcare professional for medical advice.",
            sources=medical_knowledge_service.source_list(references),
            wasShortened=outcome.was_shortened,
        )
    except Exception as exc:
        logger.error("Gemini API error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="AI service error. Please try again later.")


@router.get(
    "/languages",
    summary="Languages the assistant will answer in",
    description=(
        "The codes accepted by the `language` field of `POST "
        "/assistant/chat`. Served from the same list the request model "
        "validates against, so this cannot advertise a language the "
        "endpoint would then reject."
    ),
)
async def supported_languages(current_user: dict = Depends(get_current_user)):
    return SUPPORTED_LANGUAGES
