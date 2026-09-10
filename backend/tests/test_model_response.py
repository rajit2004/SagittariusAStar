
import pytest

from core.model_response import (
    FINISH_MAX_TOKENS,
    FINISH_OTHER,
    FINISH_RECITATION,
    FINISH_REASON_UNSPECIFIED,
    FINISH_SAFETY,
    FINISH_STOP,
    MESSAGE_EMPTY,
    MESSAGE_RECITATION,
    MESSAGE_SAFETY,
    MESSAGE_UNAVAILABLE,
    STATUS_BLOCKED_RECITATION,
    STATUS_BLOCKED_SAFETY,
    STATUS_OK,
    STATUS_TRUNCATED,
    STATUS_UNAVAILABLE,
    TRUNCATION_NOTE,
    candidate_text,
    finish_reason_name,
    finish_reason_value,
    interpret,
    response_text,
)

class FakePart:
    def __init__(self, text):
        self.text = text

class FakeContent:
    def __init__(self, texts):
        self.parts = [FakePart(t) for t in texts]

class FakeCandidate:
    def __init__(self, finish_reason, texts=()):
        self.finish_reason = finish_reason
        self.content = FakeContent(texts) if texts else FakeContent([])

class FakeResponse:

    def __init__(self, candidates, prompt_feedback=None):
        self.candidates = candidates
        if prompt_feedback is not None:
            self.prompt_feedback = prompt_feedback

    @property
    def text(self):
        raise ValueError(
            "Quick accessor for 'text' requires a valid response with "
            "non-empty candidates"
        )

class FakeTextOnlyResponse:

    def __init__(self, text, candidates=None):
        self.text = text
        self.candidates = candidates if candidates is not None else []

class ProtoLikeEnum(int):

    def __new__(cls, value, name):
        obj = super().__new__(cls, value)
        obj._name = name
        return obj

    def __str__(self):
        return f"FinishReason.{self._name}"

class FakeBlockFeedback:
    def __init__(self, block_reason):
        self.block_reason = block_reason

@pytest.mark.parametrize(
    "raw,expected",
    [
        (3, FINISH_SAFETY),
        ("3", FINISH_SAFETY),
        ("SAFETY", FINISH_SAFETY),
        ("safety", FINISH_SAFETY),
        ("FinishReason.SAFETY", FINISH_SAFETY),
        (2, FINISH_MAX_TOKENS),
        ("MAX_TOKENS", FINISH_MAX_TOKENS),
        (1, FINISH_STOP),
        ("STOP", FINISH_STOP),
        (0, FINISH_REASON_UNSPECIFIED),
        (4, FINISH_RECITATION),
        (5, FINISH_OTHER),
    ],
)
def test_finish_reason_value_reads_every_shape(raw, expected):
    assert finish_reason_value(raw) == expected

def test_finish_reason_value_reads_a_proto_like_enum():
    assert finish_reason_value(ProtoLikeEnum(FINISH_SAFETY, "SAFETY")) == FINISH_SAFETY
    assert (
        finish_reason_value(ProtoLikeEnum(FINISH_MAX_TOKENS, "MAX_TOKENS"))
        == FINISH_MAX_TOKENS
    )

@pytest.mark.parametrize("raw", [None, "", "   ", "NOT_A_REASON", object()])
def test_finish_reason_value_is_none_for_anything_unrecognized(raw):
    assert finish_reason_value(raw) is None

def test_finish_reason_value_refuses_a_bool():
    assert finish_reason_value(True) is None
    assert finish_reason_value(False) is None

def test_finish_reason_name_round_trips_and_labels_the_unknown():
    assert finish_reason_name(FINISH_SAFETY) == "SAFETY"
    assert finish_reason_name(FINISH_MAX_TOKENS) == "MAX_TOKENS"
    assert finish_reason_name(None) is None
    assert finish_reason_name(99) == "UNKNOWN_99"

def test_max_tokens_returns_the_answer_not_a_safety_accusation():
    answer = "Cramps in the first two days are common. Warmth and rest help"
    outcome = interpret(FakeResponse([FakeCandidate(FINISH_MAX_TOKENS, [answer])]))

    assert outcome.status == STATUS_TRUNCATED
    assert outcome.was_shortened is True
    assert outcome.is_answer is True
    assert outcome.from_model is True
    assert answer in outcome.text
    assert TRUNCATION_NOTE in outcome.text

    assert "safety guidelines" not in outcome.text
    assert outcome.finish_reason == "MAX_TOKENS"

def test_max_tokens_with_no_text_at_all_is_unavailable_not_truncated():
    outcome = interpret(FakeResponse([FakeCandidate(FINISH_MAX_TOKENS, [])]))

    assert outcome.status == STATUS_UNAVAILABLE
    assert outcome.text == MESSAGE_UNAVAILABLE
    assert outcome.was_shortened is False

def test_a_real_safety_block_is_detected_by_value():
    outcome = interpret(FakeResponse([FakeCandidate(FINISH_SAFETY)]))

    assert outcome.status == STATUS_BLOCKED_SAFETY
    assert outcome.text == MESSAGE_SAFETY
    assert outcome.is_answer is False
    assert outcome.from_model is False
    assert outcome.finish_reason == "SAFETY"

def test_a_safety_block_arriving_as_a_bare_number_is_still_detected():
    outcome = interpret(FakeResponse([FakeCandidate(3)]))
    assert outcome.status == STATUS_BLOCKED_SAFETY

def test_a_safety_block_arriving_as_a_name_is_still_detected():
    outcome = interpret(FakeResponse([FakeCandidate("SAFETY")]))
    assert outcome.status == STATUS_BLOCKED_SAFETY

def test_the_safety_message_does_not_blame_the_person_asking():
    lowered = MESSAGE_SAFETY.lower()
    assert "your request" not in lowered
    assert "triggered" not in lowered
    assert "healthcare professional" in lowered

def test_recitation_gets_its_own_message():
    outcome = interpret(FakeResponse([FakeCandidate(FINISH_RECITATION)]))

    assert outcome.status == STATUS_BLOCKED_RECITATION
    assert outcome.text == MESSAGE_RECITATION
    assert outcome.finish_reason == "RECITATION"

def test_other_with_text_is_still_an_answer():
    outcome = interpret(FakeResponse([FakeCandidate(FINISH_OTHER, ["Here is what I know."])]))

    assert outcome.status == STATUS_OK
    assert outcome.text == "Here is what I know."
    assert outcome.finish_reason == "OTHER"

def test_other_without_text_is_unavailable():
    outcome = interpret(FakeResponse([FakeCandidate(FINISH_OTHER)]))

    assert outcome.status == STATUS_UNAVAILABLE
    assert outcome.text == MESSAGE_EMPTY

def test_an_unknown_future_reason_with_text_is_not_treated_as_a_failure():
    outcome = interpret(FakeResponse([FakeCandidate(97, ["An answer."])]))

    assert outcome.status == STATUS_OK
    assert outcome.text == "An answer."
    assert outcome.finish_reason == "UNKNOWN_97"

def test_stop_returns_the_text_unchanged():
    outcome = interpret(FakeResponse([FakeCandidate(FINISH_STOP, ["Plain answer."])]))

    assert outcome.status == STATUS_OK
    assert outcome.text == "Plain answer."
    assert outcome.was_shortened is False
    assert outcome.from_model is True

def test_multipart_text_is_joined_in_order():
    outcome = interpret(
        FakeResponse([FakeCandidate(FINISH_STOP, ["Part one. ", "Part two."])])
    )
    assert outcome.text == "Part one. Part two."

def test_text_is_read_from_parts_even_when_the_accessor_raises():
    response = FakeResponse([FakeCandidate(FINISH_MAX_TOKENS, ["Reachable."])])

    with pytest.raises(ValueError):
        _ = response.text

    assert candidate_text(response.candidates[0]) == "Reachable."
    assert "Reachable." in interpret(response).text

def test_response_text_falls_back_to_the_accessor_when_parts_are_absent():
    assert response_text(FakeTextOnlyResponse("  From the accessor.  ")) == (
        "From the accessor."
    )

def test_response_text_is_empty_rather_than_raising():
    assert response_text(FakeResponse([])) == ""

def test_no_candidates_and_no_text_is_unavailable():
    outcome = interpret(FakeResponse([]))

    assert outcome.status == STATUS_UNAVAILABLE
    assert outcome.text == MESSAGE_UNAVAILABLE
    assert outcome.finish_reason is None

def test_no_candidates_but_readable_text_is_still_an_answer():
    outcome = interpret(FakeTextOnlyResponse("An answer with no candidate list."))

    assert outcome.status == STATUS_OK
    assert outcome.text == "An answer with no candidate list."
    assert outcome.from_model is True

def test_a_prompt_level_block_reads_as_a_safety_block():
    outcome = interpret(
        FakeResponse([], prompt_feedback=FakeBlockFeedback("BlockReason.SAFETY"))
    )

    assert outcome.status == STATUS_BLOCKED_SAFETY
    assert outcome.text == MESSAGE_SAFETY
    assert outcome.finish_reason == "SAFETY"

def test_an_unspecified_block_reason_is_not_reported_as_a_safety_block():
    outcome = interpret(
        FakeResponse(
            [], prompt_feedback=FakeBlockFeedback("BLOCK_REASON_UNSPECIFIED")
        )
    )

    assert outcome.status == STATUS_UNAVAILABLE

@pytest.mark.parametrize(
    "finish_reason",
    [FINISH_REASON_UNSPECIFIED, FINISH_STOP, FINISH_MAX_TOKENS, FINISH_SAFETY,
     FINISH_RECITATION, FINISH_OTHER, 97, None, "nonsense"],
)
def test_every_outcome_carries_showable_text(finish_reason):
    outcome = interpret(FakeResponse([FakeCandidate(finish_reason)]))

    assert isinstance(outcome.text, str)
    assert outcome.text.strip()

def test_interpret_never_raises_on_a_malformed_response():
    class Nothing:
        pass

    outcome = interpret(Nothing())
    assert outcome.status == STATUS_UNAVAILABLE
    assert outcome.text
