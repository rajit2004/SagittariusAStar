
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Sequence

from services.prediction_service import (
    CONFIDENCE_LOW,
    Prediction,
    SOURCE_DEFAULT,
    predict,
)

GSM7_SINGLE_SEGMENT = 160

UCS2_SINGLE_SEGMENT = 70

UCS2_CONCATENATED_SEGMENT = 67

UCS2_MAX_SEGMENTS = 2

GSM7_BASIC = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)

GSM7_EXTENDED = set("^{}\\[~]|€")

def is_gsm7(text: str) -> bool:
    return all(char in GSM7_BASIC or char in GSM7_EXTENDED for char in text)

def gsm7_length(text: str) -> int:
    return sum(2 if char in GSM7_EXTENDED else 1 for char in text)

def segment_budget(text: str) -> int:
    if is_gsm7(text):
        return GSM7_SINGLE_SEGMENT
    return UCS2_CONCATENATED_SEGMENT * UCS2_MAX_SEGMENTS

def measured_length(text: str) -> int:
    return gsm7_length(text) if is_gsm7(text) else len(text)

GSM7_ELLIPSIS = "..."
UCS2_ELLIPSIS = "…"

def ellipsis_for(text: str) -> str:
    return GSM7_ELLIPSIS if is_gsm7(text) else UCS2_ELLIPSIS

def fit_to_budget(text: str) -> str:
    budget = segment_budget(text)
    if measured_length(text) <= budget:
        return text

    marker = ellipsis_for(text)
    room = budget - measured_length(marker)

    clipped = text[:room]
    if " " in clipped:
        clipped = clipped[: clipped.rindex(" ")]
    return clipped.rstrip(" .,।") + marker

@dataclass(frozen=True)
class SummaryTemplates:

    overdue: str

    due_today: str

    upcoming: str

    unmeasured: str

    no_anchor: str

    disclaimer: str

TEMPLATES: Dict[str, SummaryTemplates] = {
    "en": SummaryTemplates(
        overdue="Rhythma: day {day} of your cycle. Your period is {days} days late.",
        due_today="Rhythma: day {day} of your cycle. Your period is expected today.",
        upcoming="Rhythma Summary: Cycle Day {day}/{length}. Next period expected in ~{days} days.",
        unmeasured="Rhythma: day {day} of your cycle. Log a few periods for a prediction based on your own cycles.",
        no_anchor="Rhythma: no period logged yet. Log your last period to get a prediction.",
        disclaimer=" Estimate only, not medical/contraceptive advice.",
    ),
    "hi": SummaryTemplates(
        overdue="रिदमा: चक्र का दिन {day}। मासिक धर्म {days} दिन देर से है।",
        due_today="रिदमा: चक्र का दिन {day}। मासिक धर्म आज अपेक्षित है।",
        upcoming="रिदमा: चक्र का दिन {day}/{length}। अगला मासिक ~{days} दिन में।",
        unmeasured="रिदमा: चक्र का दिन {day}। अपने चक्र के अनुमान के लिए कुछ मासिक दर्ज करें।",
        no_anchor="रिदमा: अभी कोई मासिक दर्ज नहीं है। अनुमान के लिए पिछला मासिक दर्ज करें।",
        disclaimer=" केवल अनुमान, चिकित्सा या गर्भनिरोधक सलाह नहीं।",
    ),
    "mr": SummaryTemplates(
        overdue="रिदमा: चक्राचा दिवस {day}। पाळी {days} दिवस उशिरा आहे।",
        due_today="रिदमा: चक्राचा दिवस {day}। पाळी आज अपेक्षित आहे।",
        upcoming="रिदमा: चक्राचा दिवस {day}/{length}। पुढील पाळी ~{days} दिवसांत।",
        unmeasured="रिदमा: चक्राचा दिवस {day}। स्वतःच्या अंदाजासाठी काही पाळ्या नोंदवा।",
        no_anchor="रिदमा: अद्याप पाळी नोंदलेली नाही। अंदाजासाठी मागील पाळी नोंदवा।",
        disclaimer=" फक्त अंदाज, वैद्यकीय किंवा गर्भनिरोधक सल्ला नाही।",
    ),
    "ta": SummaryTemplates(
        overdue="ரித்மா: சுழற்சி நாள் {day}. மாதவிடாய் {days} நாள் தாமதம்.",
        due_today="ரித்மா: சுழற்சி நாள் {day}. மாதவிடாய் இன்று எதிர்பார்க்கப்படுகிறது.",
        upcoming="ரித்மா: சுழற்சி நாள் {day}/{length}. அடுத்த மாதவிடாய் ~{days} நாளில்.",
        unmeasured="ரித்மா: சுழற்சி நாள் {day}. உங்கள் சொந்த கணிப்புக்கு சில மாதவிடாய்களைப் பதிவு செய்யவும்.",
        no_anchor="ரித்மா: இதுவரை மாதவிடாய் பதிவு இல்லை. கணிப்புக்கு கடைசி மாதவிடாயைப் பதிவு செய்யவும்.",
        disclaimer=" மதிப்பீடு மட்டுமே, மருத்துவ ஆலோசனை அல்ல.",
    ),
    "te": SummaryTemplates(
        overdue="రిథ్మా: చక్ర దినం {day}. రుతుస్రావం {days} రోజులు ఆలస్యం.",
        due_today="రిథ్మా: చక్ర దినం {day}. రుతుస్రావం ఈరోజు ఆశించబడుతోంది.",
        upcoming="రిథ్మా: చక్ర దినం {day}/{length}. తదుపరి రుతుస్రావం ~{days} రోజుల్లో.",
        unmeasured="రిథ్మా: చక్ర దినం {day}. మీ సొంత అంచనా కోసం కొన్ని రుతుస్రావాలు నమోదు చేయండి.",
        no_anchor="రిథ్మా: ఇంకా రుతుస్రావం నమోదు కాలేదు. అంచనా కోసం చివరిది నమోదు చేయండి.",
        disclaimer=" అంచనా మాత్రమే, వైద్య సలహా కాదు.",
    ),
    "kn": SummaryTemplates(
        overdue="ರಿದ್ಮಾ: ಚಕ್ರದ ದಿನ {day}. ಮುಟ್ಟು {days} ದಿನ ತಡವಾಗಿದೆ.",
        due_today="ರಿದ್ಮಾ: ಚಕ್ರದ ದಿನ {day}. ಮುಟ್ಟು ಇಂದು ನಿರೀಕ್ಷಿತ.",
        upcoming="ರಿದ್ಮಾ: ಚಕ್ರದ ದಿನ {day}/{length}. ಮುಂದಿನ ಮುಟ್ಟು ~{days} ದಿನಗಳಲ್ಲಿ.",
        unmeasured="ರಿದ್ಮಾ: ಚಕ್ರದ ದಿನ {day}. ನಿಮ್ಮದೇ ಅಂದಾಜಿಗಾಗಿ ಕೆಲವು ಮುಟ್ಟುಗಳನ್ನು ದಾಖಲಿಸಿ.",
        no_anchor="ರಿದ್ಮಾ: ಇನ್ನೂ ಮುಟ್ಟು ದಾಖಲಾಗಿಲ್ಲ. ಅಂದಾಜಿಗಾಗಿ ಕೊನೆಯದನ್ನು ದಾಖಲಿಸಿ.",
        disclaimer=" ಅಂದಾಜು ಮಾತ್ರ, ವೈದ್ಯಕೀಯ ಸಲಹೆಯಲ್ಲ.",
    ),
    "ml": SummaryTemplates(
        overdue="റിഥ്മ: ചക്ര ദിനം {day}. ആർത്തവം {days} ദിവസം വൈകി.",
        due_today="റിഥ്മ: ചക്ര ദിനം {day}. ആർത്തവം ഇന്ന് പ്രതീക്ഷിക്കുന്നു.",
        upcoming="റിഥ്മ: ചക്ര ദിനം {day}/{length}. അടുത്ത ആർത്തവം ~{days} ദിവസത്തിൽ.",
        unmeasured="റിഥ്മ: ചക്ര ദിനം {day}. സ്വന്തം പ്രവചനത്തിനായി കുറച്ച് ആർത്തവങ്ങൾ രേഖപ്പെടുത്തുക.",
        no_anchor="റിഥ്മ: ആർത്തവം രേഖപ്പെടുത്തിയിട്ടില്ല. പ്രവചനത്തിനായി അവസാനത്തേത് രേഖപ്പെടുത്തുക.",
        disclaimer=" കണക്കാക്കൽ മാത്രം, വൈദ്യോപദേശമല്ല.",
    ),
    "gu": SummaryTemplates(
        overdue="રિધ્મા: ચક્રનો દિવસ {day}. માસિક {days} દિવસ મોડું છે.",
        due_today="રિધ્મા: ચક્રનો દિવસ {day}. માસિક આજે અપેક્ષિત છે.",
        upcoming="રિધ્મા: ચક્રનો દિવસ {day}/{length}. આગામી માસિક ~{days} દિવસમાં.",
        unmeasured="રિધ્મા: ચક્રનો દિવસ {day}. તમારા પોતાના અંદાજ માટે થોડા માસિક નોંધો.",
        no_anchor="રિધ્મા: હજુ કોઈ માસિક નોંધાયું નથી. અંદાજ માટે છેલ્લું નોંધો.",
        disclaimer=" માત્ર અંદાજ, તબીબી સલાહ નથી.",
    ),
}

DEFAULT_LANGUAGE = "en"

SUPPORTED_SMS_LANGUAGES = frozenset(TEMPLATES)

SITUATION_NO_ANCHOR = "no_anchor"
SITUATION_UNMEASURED = "unmeasured"
SITUATION_OVERDUE = "overdue"
SITUATION_DUE_TODAY = "due_today"
SITUATION_UPCOMING = "upcoming"

def resolve_language(profile: Optional[Dict[str, Any]]) -> str:
    raw = (profile or {}).get("language")
    if not isinstance(raw, str):
        return DEFAULT_LANGUAGE

    code = raw.strip().lower().replace("_", "-").split("-")[0]
    return code if code in TEMPLATES else DEFAULT_LANGUAGE

def _situation_for(prediction: Prediction) -> str:
    if prediction.last_period_start is None or prediction.days_until_next_period is None:
        return SITUATION_NO_ANCHOR

    if (
        prediction.cycle_length.source == SOURCE_DEFAULT
        and prediction.cycle_length.sample_size == 0
        and not prediction.is_overdue
    ):
        return SITUATION_UNMEASURED

    if prediction.is_overdue:
        return SITUATION_OVERDUE
    if prediction.days_until_next_period == 0:
        return SITUATION_DUE_TODAY
    return SITUATION_UPCOMING

def _render(templates: SummaryTemplates, situation: str, prediction: Prediction) -> str:
    sentence = getattr(templates, situation)
    return sentence.format(
        day=prediction.current_cycle_day,
        length=prediction.cycle_length.days,
        days=(
            prediction.days_overdue
            if situation == SITUATION_OVERDUE
            else prediction.days_until_next_period
        ),
    )

def compose(prediction: Prediction, language: str = DEFAULT_LANGUAGE) -> str:
    templates = TEMPLATES.get(language, TEMPLATES[DEFAULT_LANGUAGE])
    situation = _situation_for(prediction)
    summary = _render(templates, situation, prediction)

    combined = summary + templates.disclaimer
    if measured_length(combined) <= segment_budget(combined):
        return combined
    return fit_to_budget(summary)

def build_summary(
    logs: Sequence[Dict[str, Any]],
    profile: Optional[Dict[str, Any]] = None,
    today: Optional[date] = None,
) -> str:
    prediction = predict(logs, profile=profile, today=today)
    return compose(prediction, resolve_language(profile))

def describe(
    logs: Sequence[Dict[str, Any]],
    profile: Optional[Dict[str, Any]] = None,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    prediction = predict(logs, profile=profile, today=today)
    language = resolve_language(profile)
    body = compose(prediction, language)

    return {
        "body": body,
        "language": language,
        "situation": _situation_for(prediction),
        "encoding": "GSM-7" if is_gsm7(body) else "UCS-2",
        "length": measured_length(body),
        "budget": segment_budget(body),
        "confidence": prediction.cycle_length.confidence,
        "estimateSource": prediction.cycle_length.source,
        "isOverdue": prediction.is_overdue,
        "daysOverdue": prediction.days_overdue,
        "daysUntilNextPeriod": prediction.days_until_next_period,
    }

def template_placeholders() -> Dict[str, List[str]]:
    import string

    reference = TEMPLATES[DEFAULT_LANGUAGE]
    return {
        situation: sorted(
            {
                name
                for _, name, _, _ in string.Formatter().parse(getattr(reference, situation))
                if name
            }
        )
        for situation in (
            SITUATION_OVERDUE,
            SITUATION_DUE_TODAY,
            SITUATION_UPCOMING,
            SITUATION_UNMEASURED,
            SITUATION_NO_ANCHOR,
        )
    }

__all__ = [
    "DEFAULT_LANGUAGE",
    "GSM7_ELLIPSIS",
    "GSM7_SINGLE_SEGMENT",
    "UCS2_ELLIPSIS",
    "ellipsis_for",
    "SITUATION_DUE_TODAY",
    "SITUATION_NO_ANCHOR",
    "SITUATION_OVERDUE",
    "SITUATION_UNMEASURED",
    "SITUATION_UPCOMING",
    "SUPPORTED_SMS_LANGUAGES",
    "TEMPLATES",
    "UCS2_CONCATENATED_SEGMENT",
    "UCS2_MAX_SEGMENTS",
    "SummaryTemplates",
    "build_summary",
    "compose",
    "describe",
    "fit_to_budget",
    "gsm7_length",
    "is_gsm7",
    "measured_length",
    "resolve_language",
    "segment_budget",
    "template_placeholders",
]
