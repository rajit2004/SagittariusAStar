
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

logger = logging.getLogger(__name__)

DEFAULT_DATASET_PATH = Path(__file__).resolve().parent.parent / "data" / "medical_references.json"

DEFAULT_RETRIEVAL_LIMIT = 3

DEFAULT_MAX_FACTS_PER_ENTRY = 4

@dataclass(frozen=True)
class MedicalReference:

    id: str
    topic: str
    summary: str
    facts: Tuple[str, ...]
    keywords: Tuple[str, ...]
    symptom_tags: Tuple[str, ...]
    source: str
    source_title: str
    source_url: str
    reviewed_on: str
    accessed_on: str
    language: str = "en"

def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()

def _tokens(text: str) -> set:
    return {t for t in _normalize(text).split() if len(t) >= 3}

class MedicalKnowledgeService:

    def __init__(self, dataset_path: Optional[Union[str, Path]] = None):
        self._dataset_path = Path(dataset_path) if dataset_path else DEFAULT_DATASET_PATH
        self._references = self._load()

    def _load(self) -> List[MedicalReference]:
        try:
            with open(self._dataset_path, encoding="utf-8") as fh:
                payload = json.load(fh)
        except (OSError, ValueError) as exc:
            logger.warning(
                "Could not load medical reference dataset %s: %s",
                self._dataset_path,
                exc,
            )
            return []

        references: List[MedicalReference] = []
        for raw in payload.get("references", []) or []:
            references.append(
                MedicalReference(
                    id=str(raw.get("id", "")),
                    topic=str(raw.get("topic", "")),
                    summary=str(raw.get("summary", "")),
                    facts=tuple(str(f) for f in raw.get("facts", []) or []),
                    keywords=tuple(str(k) for k in raw.get("keywords", []) or []),
                    symptom_tags=tuple(str(t) for t in raw.get("symptomTags", []) or []),
                    source=str(raw.get("source", "")),
                    source_title=str(raw.get("sourceTitle", "")),
                    source_url=str(raw.get("sourceUrl", "")),
                    reviewed_on=str(raw.get("reviewedOn", "")),
                    accessed_on=str(raw.get("accessedOn", "")),
                    language=str(raw.get("language", "en")),
                )
            )
        return references

    def all_references(self) -> List[MedicalReference]:
        return list(self._references)

    def retrieve(self, query: str, limit: int = DEFAULT_RETRIEVAL_LIMIT) -> List[MedicalReference]:
        if not query or not self._references:
            return []

        normalized_query = _normalize(query)
        query_tokens = _tokens(normalized_query)
        scored: List[Tuple[int, int, MedicalReference]] = []

        for index, ref in enumerate(self._references):
            haystack = _normalize(
                " ".join(ref.keywords)
                + " "
                + " ".join(ref.symptom_tags)
                + " "
                + ref.topic
            )
            haystack_tokens = _tokens(haystack)
            score = 0

            for keyword in ref.keywords:
                if _normalize(keyword) in normalized_query:
                    score += 3

            score += sum(1 for token in query_tokens if token in haystack_tokens)

            if score > 0:
                scored.append((score, index, ref))

        scored.sort(key=lambda item: (-item[0], item[1]))
        return [ref for _, _, ref in scored[:limit]]

    def source_list(
        self,
        references: Sequence[MedicalReference],
    ) -> List[Dict[str, str]]:
        return [
            {
                "name": ref.source,
                "title": ref.source_title,
                "url": ref.source_url,
                "accessedOn": ref.accessed_on,
            }
            for ref in (references or [])
        ]

    def build_grounding_block(
        self,
        references: Sequence[MedicalReference],
        max_facts_per_entry: int = DEFAULT_MAX_FACTS_PER_ENTRY,
    ) -> Optional[str]:
        references = list(references or [])
        if not references:
            return None

        lines = [
            "--- Trusted Medical Reference ---",
            "The facts below were retrieved from credible health sources. When they are "
            "relevant to the user's question, base your answer on them and on nothing "
            "beyond them: do not add medical claims that are not present here. If the "
            "question is not covered by these facts, say so honestly and suggest "
            "consulting a qualified healthcare professional. Attribute each fact to its "
            "source by name when you use it.",
        ]

        for ref in references:
            lines.append("")
            lines.append(f"Topic: {ref.topic}")
            for fact in ref.facts[:max_facts_per_entry]:
                lines.append(f"- {fact}")
            lines.append(f"Source: {ref.source} ({ref.source_title}) - {ref.source_url}")

        return "\n".join(lines)

__all__ = [
    "DEFAULT_DATASET_PATH",
    "DEFAULT_MAX_FACTS_PER_ENTRY",
    "DEFAULT_RETRIEVAL_LIMIT",
    "MedicalKnowledgeService",
    "MedicalReference",
]
