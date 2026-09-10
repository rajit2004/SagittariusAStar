

from core.model_response import (  # noqa: E402
    MESSAGE_SAFETY,
    STATUS_BLOCKED_SAFETY,
    STATUS_UNAVAILABLE,
    interpret,
)


class MockCandidate:
    def __init__(self, finish_reason, text=None):
        self.finish_reason = finish_reason
        self.content = MockContent(text)


class MockContent:
    def __init__(self, text):
        self.parts = [MockPart(text)] if text else []


class MockPart:
    def __init__(self, text):
        self.text = text


class MockBlockedResponse:
    def __init__(self, finish_reason="SAFETY", text=None):
        self.candidates = [MockCandidate(finish_reason, text)]

    @property
    def text(self):
        raise ValueError(
            "Quick accessor for 'text' requires a valid response with "
            "non-empty candidates"
        )


def test_gemini_safety_response_handling():
    """A safety-blocked candidate produces the safety message."""
    outcome = interpret(MockBlockedResponse("SAFETY"))

    assert outcome.status == STATUS_BLOCKED_SAFETY
    assert outcome.text == MESSAGE_SAFETY
    assert outcome.is_answer is False


def test_gemini_safety_response_handling_by_numeric_reason():
    """The same block arriving as the bare value 3 rather than the name.

    The old string match required the name; this is the case that fell
    through it into `response.text`, which raises.
    """
    outcome = interpret(MockBlockedResponse(3))

    assert outcome.status == STATUS_BLOCKED_SAFETY
    assert outcome.text == MESSAGE_SAFETY


def test_gemini_value_error_fallback():
    """An unrecognized reason with no text still yields showable text.

    `MockBlockedResponse.text` raises, exactly as the SDK accessor does on
    a candidate with no readable parts. Nothing may propagate out of
    `interpret`.
    """
    outcome = interpret(MockBlockedResponse("UNKNOWN"))

    assert outcome.status == STATUS_UNAVAILABLE
    assert outcome.text.strip()
    assert outcome.is_answer is False
