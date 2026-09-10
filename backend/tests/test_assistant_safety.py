
from core.model_response import (
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
    outcome = interpret(MockBlockedResponse("SAFETY"))

    assert outcome.status == STATUS_BLOCKED_SAFETY
    assert outcome.text == MESSAGE_SAFETY
    assert outcome.is_answer is False

def test_gemini_safety_response_handling_by_numeric_reason():
    outcome = interpret(MockBlockedResponse(3))

    assert outcome.status == STATUS_BLOCKED_SAFETY
    assert outcome.text == MESSAGE_SAFETY

def test_gemini_value_error_fallback():
    outcome = interpret(MockBlockedResponse("UNKNOWN"))

    assert outcome.status == STATUS_UNAVAILABLE
    assert outcome.text.strip()
    assert outcome.is_answer is False
