
from __future__ import annotations

from typing import Callable, Dict, Optional

from services.chat_link_service import (
    CODE_LENGTH,
    normalize_code,
    redeem_link_code,
    unlink,
)
from services.scoring_service import get_user_scores
from utils.logger import logger

CHANNEL_LABELS: Dict[str, str] = {
    "telegram": "Telegram",
    "whatsapp": "WhatsApp",
}

HELP_TEXT = (
    "Rhythma\n"
    "\n"
    "status — your cycle day and when your next period is expected\n"
    "link <code> — connect this chat to your Rhythma account\n"
    "unlink — disconnect this chat\n"
    "help — this message\n"
    "\n"
    "Rhythma cannot give medical advice here. For anything urgent, "
    "please see a health worker or doctor."
)

LINK_PROMPT = (
    "This chat is not connected to a Rhythma account yet, so there is "
    "nothing personal to show.\n"
    "\n"
    "Open Rhythma, go to Settings, and generate a connection code. Then "
    "send it here as: link ABCD2345"
)

LINK_BAD_CODE = (
    "That code did not work. Codes expire after a few minutes and can "
    "only be used once — generate a new one in Rhythma and send it again."
)

LINK_MISSING_CODE = (
    "Send the code with the command, like this: link ABCD2345"
)

LINK_OK = (
    "Done — this chat is now connected to your Rhythma account. "
    "Send 'status' for your cycle day, or 'unlink' to disconnect."
)

UNLINK_OK = (
    "This chat is no longer connected to a Rhythma account. Nothing "
    "personal will be sent here."
)

UNLINK_NONE = "This chat was not connected to a Rhythma account."

EMPTY_MESSAGE = "Send 'help' to see what Rhythma can do here."

STATUS_UNAVAILABLE = (
    "Rhythma could not read your cycle data just now. Please try again "
    "in a few minutes, or open the app."
)

DISCLAIMER = "Estimate only, not medical or contraceptive advice."

def _channel_label(channel: str) -> str:
    return CHANNEL_LABELS.get(channel, channel.capitalize() if channel else "chat")

def _split_command(text: str) -> tuple[str, str]:
    stripped = (text or "").strip()
    if not stripped:
        return "", ""
    head, _, tail = stripped.partition(" ")
    return head.lstrip("/").lower(), tail.strip()

class ChatbotService:

    @staticmethod
    def process_incoming_message(
        text: str,
        channel: str = "telegram",
        chat_id: str = "",
        user_id: Optional[str] = None,
    ) -> str:
        command, argument = _split_command(text)

        if not command:
            return EMPTY_MESSAGE

        handler = _COMMANDS.get(command)
        if handler is not None:
            return handler(channel, chat_id, user_id, argument)

        if user_id is None:
            return LINK_PROMPT
        return (
            "Rhythma cannot answer health questions over "
            f"{_channel_label(channel)} yet. Open the app to ask the "
            "assistant, or send 'status' for your cycle day."
        )

    @staticmethod
    def _help(channel: str, chat_id: str, user_id: Optional[str], argument: str) -> str:
        if user_id is None:
            return f"{HELP_TEXT}\n\n{LINK_PROMPT}"
        return HELP_TEXT

    @staticmethod
    def _status(channel: str, chat_id: str, user_id: Optional[str], argument: str) -> str:
        if user_id is None:
            return LINK_PROMPT

        try:
            score_data = get_user_scores(user_id)
        except Exception as exc:

            logger.bind(channel=channel).warning(
                f"Chatbot could not load cycle status: {exc}"
            )
            return STATUS_UNAVAILABLE

        logs = score_data.get("logs") or []
        if not logs:
            return (
                "No cycles are logged yet, so there is nothing to "
                "summarise. Log a period in Rhythma and send 'status' "
                "again."
            )

        from datetime import date

        from services.prediction_service import predict

        prediction = predict(logs, profile=score_data.get("profile"), today=date.today())

        lines = [f"Rhythma — cycle day {prediction.current_cycle_day or 1}."]

        if prediction.is_overdue:
            days = prediction.days_overdue or 0
            lines.append(
                f"Your period is {days} day{'s' if days != 1 else ''} later "
                "than expected."
            )
        elif prediction.days_until_next_period is not None:
            days = prediction.days_until_next_period
            if days == 0:
                lines.append("Your period is expected today.")
            else:
                lines.append(
                    f"Next period expected in about {days} "
                    f"day{'s' if days != 1 else ''}."
                )

        lines.append(DISCLAIMER)
        return " ".join(lines)

    @staticmethod
    def _link(channel: str, chat_id: str, user_id: Optional[str], argument: str) -> str:
        if user_id is not None:
            return "This chat is already connected. Send 'unlink' first to connect a different account."

        code = normalize_code(argument)
        if not code:
            return LINK_MISSING_CODE
        if len(code) != CODE_LENGTH:
            return LINK_BAD_CODE

        linked_user = redeem_link_code(channel, chat_id, code)
        if linked_user is None:
            return LINK_BAD_CODE
        return LINK_OK

    @staticmethod
    def _unlink(channel: str, chat_id: str, user_id: Optional[str], argument: str) -> str:
        return UNLINK_OK if unlink(channel, chat_id) else UNLINK_NONE

_Handler = Callable[[str, str, Optional[str], str], str]

_COMMANDS: Dict[str, _Handler] = {
    "help": ChatbotService._help,
    "commands": ChatbotService._help,
    "start": ChatbotService._help,
    "status": ChatbotService._status,
    "cycle": ChatbotService._status,
    "period": ChatbotService._status,
    "link": ChatbotService._link,
    "connect": ChatbotService._link,
    "unlink": ChatbotService._unlink,
    "stop": ChatbotService._unlink,
    "disconnect": ChatbotService._unlink,
}

__all__ = ["ChatbotService", "DISCLAIMER", "HELP_TEXT", "LINK_PROMPT"]
