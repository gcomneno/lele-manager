from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from typing import Any, Literal, TypeAlias
import unicodedata

from lele_manager.core.exact_duplicates import is_exact_duplicate_record


Reason: TypeAlias = Literal[
    "same-topic",
    "shared-tags",
    "similarity-gate",
    "negated-shared-phrase",
    "opposing-modal-cue",
    "opposing-term-cue",
    "version-or-date-context",
    "different-source-context",
]
AuxiliaryDecision: TypeAlias = Literal["different-context", "dismissed"]

CONTRADICTION_REVIEW_REASONS: tuple[Reason, ...] = (
    "same-topic",
    "shared-tags",
    "similarity-gate",
    "negated-shared-phrase",
    "opposing-modal-cue",
    "opposing-term-cue",
    "version-or-date-context",
    "different-source-context",
)
AUXILIARY_DECISIONS: tuple[AuxiliaryDecision, ...] = ("different-context", "dismissed")
GENERATOR_VERSION = 1
DEFAULT_SIMILARITY_THRESHOLD = 0.82
REVIEWABLE_LIFECYCLES = ("active", "review-needed")

_SUBJECT_REASON_ORDER: tuple[Reason, ...] = ("same-topic", "shared-tags", "similarity-gate")
_TENSION_REASON_ORDER: tuple[Reason, ...] = (
    "negated-shared-phrase",
    "opposing-modal-cue",
    "opposing-term-cue",
    "version-or-date-context",
    "different-source-context",
)
_MODAL_PAIRS = (
    ("must", "must not"),
    ("should", "should not"),
    ("always", "never"),
    ("required", "forbidden"),
    ("allow", "deny"),
    ("allowed", "disallowed"),
    ("enable", "disable"),
)
_OPPOSING_TERM_PAIRS = (
    ("increase", "decrease"),
    ("include", "exclude"),
    ("accept", "reject"),
    ("sync", "async"),
    ("public", "private"),
    ("mutable", "immutable"),
)
_VERSION_PATTERN = re.compile(r"\b(?:v?\d+(?:\.\d+)+|20\d{2}(?:-\d{2}){0,2})\b", re.IGNORECASE)
_WORD_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9'-]*")


@dataclass(frozen=True, slots=True)
class PairIdentity:
    left_id: str
    right_id: str

    @classmethod
    def from_ids(cls, left_id: object, right_id: object) -> "PairIdentity":
        left = _id(left_id)
        right = _id(right_id)
        if not left or not right or left == right:
            raise ValueError("pair identity requires two distinct non-empty stable lesson IDs")
        if right < left:
            left, right = right, left
        return cls(left, right)

    def as_tuple(self) -> tuple[str, str]:
        return self.left_id, self.right_id


@dataclass(frozen=True, slots=True)
class ContradictionCandidate:
    pair: PairIdentity
    left_id: str
    right_id: str
    reasons: tuple[Reason, ...]
    same_subject_reasons: tuple[Reason, ...]
    tension_reasons: tuple[Reason, ...]
    left_title: str
    right_title: str
    left_lifecycle: str
    right_lifecycle: str
    similarity_score: float | None = None


def validate_reason(value: str) -> Reason:
    if value not in CONTRADICTION_REVIEW_REASONS:
        raise ValueError(f"unknown contradiction-review reason: {value}")
    return value


def validate_auxiliary_decision(value: str) -> AuxiliaryDecision:
    if value not in AUXILIARY_DECISIONS:
        raise ValueError(f"unknown contradiction-review decision: {value}")
    return value


def material_fingerprint(lesson: Mapping[str, Any]) -> str:
    canonical = {
        "text": _text(lesson.get("text", lesson.get("body"))),
        "title": _short(lesson.get("title")),
        "topic": _short(lesson.get("topic")),
        "source": _short(lesson.get("source")),
        "date": _date(lesson.get("date")),
        "tags": _tags(lesson.get("tags")),
        "lifecycle": _short(lesson.get("lifecycle")),
        "superseded_by": _short(lesson.get("superseded_by")),
        "relationships": _relationships(lesson.get("relationships")),
    }
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def generate_contradiction_candidates(
    lessons: Sequence[Mapping[str, Any]],
    *,
    similarity_scores: Mapping[tuple[str, str], float] | None = None,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    analysis_bound: int | None = None,
) -> tuple[ContradictionCandidate, ...]:
    if not math.isfinite(similarity_threshold) or not 0.0 <= similarity_threshold <= 1.0:
        raise ValueError("similarity_threshold must be between 0 and 1")
    if analysis_bound is not None and analysis_bound < 1:
        raise ValueError("analysis_bound must be at least 1")

    snapshots = [dict(lesson) for lesson in lessons]
    indexed = sorted(snapshots, key=lambda lesson: _id(lesson.get("id")))
    candidates: list[ContradictionCandidate] = []
    pairs_seen = 0
    for left_index, left in enumerate(indexed):
        for right in indexed[left_index + 1 :]:
            pairs_seen += 1
            if analysis_bound is not None and pairs_seen > analysis_bound:
                return tuple(sorted(candidates, key=_candidate_sort_key))
            candidate = _candidate(left, right, similarity_scores, similarity_threshold)
            if candidate is not None:
                candidates.append(candidate)
    return tuple(sorted(candidates, key=_candidate_sort_key))


def _candidate(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    similarity_scores: Mapping[tuple[str, str], float] | None,
    similarity_threshold: float,
) -> ContradictionCandidate | None:
    try:
        pair = PairIdentity.from_ids(left.get("id"), right.get("id"))
    except ValueError:
        return None
    if _short(left.get("lifecycle")) not in REVIEWABLE_LIFECYCLES:
        return None
    if _short(right.get("lifecycle")) not in REVIEWABLE_LIFECYCLES:
        return None
    if _canonically_resolved(left, right, pair) or is_exact_duplicate_record(left, right):
        return None

    score = _similarity_score(similarity_scores, pair)
    subject = _same_subject_reasons(left, right, score, similarity_threshold)
    if not subject:
        return None
    tension = _tension_reasons(left, right)
    if not tension:
        return None

    reasons = tuple(reason for reason in CONTRADICTION_REVIEW_REASONS if reason in subject or reason in tension)
    return ContradictionCandidate(
        pair=pair,
        left_id=pair.left_id,
        right_id=pair.right_id,
        reasons=reasons,
        same_subject_reasons=tuple(reason for reason in _SUBJECT_REASON_ORDER if reason in subject),
        tension_reasons=tuple(reason for reason in _TENSION_REASON_ORDER if reason in tension),
        left_title=_display(left.get("title")),
        right_title=_display(right.get("title")),
        left_lifecycle=_short(left.get("lifecycle")),
        right_lifecycle=_short(right.get("lifecycle")),
        similarity_score=score if score is not None else None,
    )


def _same_subject_reasons(
    left: Mapping[str, Any], right: Mapping[str, Any], score: float | None, threshold: float
) -> set[Reason]:
    reasons: set[Reason] = set()
    left_topic = _short(left.get("topic"))
    if left_topic and left_topic == _short(right.get("topic")):
        reasons.add("same-topic")
    if set(_tags(left.get("tags"))) & set(_tags(right.get("tags"))):
        reasons.add("shared-tags")
    if score is not None and score >= threshold:
        reasons.add("similarity-gate")
    return reasons


def _tension_reasons(left: Mapping[str, Any], right: Mapping[str, Any]) -> set[Reason]:
    left_text = _short_text(left.get("text", left.get("body")))
    right_text = _short_text(right.get("text", right.get("body")))
    reasons: set[Reason] = set()
    if _has_negated_shared_phrase(left_text, right_text):
        reasons.add("negated-shared-phrase")
    if _has_opposing_pair(left_text, right_text, _MODAL_PAIRS):
        reasons.add("opposing-modal-cue")
    if _has_opposing_pair(left_text, right_text, _OPPOSING_TERM_PAIRS):
        reasons.add("opposing-term-cue")
    if _date(left.get("date")) and _date(right.get("date")) and _date(left.get("date")) != _date(right.get("date")):
        reasons.add("version-or-date-context")
    elif set(_VERSION_PATTERN.findall(left_text)) ^ set(_VERSION_PATTERN.findall(right_text)):
        reasons.add("version-or-date-context")
    left_source = _short(left.get("source"))
    right_source = _short(right.get("source"))
    if left_source and right_source and left_source != right_source:
        reasons.add("different-source-context")
    return reasons


def _has_negated_shared_phrase(left: str, right: str) -> bool:
    for first, second in ((left, right), (right, left)):
        for phrase in _phrases(first):
            if f"not {phrase}" in second or f"no {phrase}" in second or f"without {phrase}" in second:
                return True
    return False


def _phrases(text: str) -> set[str]:
    tokens = _WORD_PATTERN.findall(text)
    stop = {"do", "does", "not", "no", "without", "must", "should", "always", "never", "the", "a", "an"}
    cleaned = [token for token in tokens if token not in stop]
    phrases = set(cleaned)
    phrases.update(" ".join(cleaned[index : index + 2]) for index in range(len(cleaned) - 1))
    phrases.update(" ".join(cleaned[index : index + 3]) for index in range(len(cleaned) - 2))
    return {phrase for phrase in phrases if len(phrase) >= 4}


def _has_opposing_pair(left: str, right: str, pairs: tuple[tuple[str, str], ...]) -> bool:
    return any(
        (_contains(left, a) and _contains(right, b)) or (_contains(left, b) and _contains(right, a))
        for a, b in pairs
    )


def _contains(text: str, phrase: str) -> bool:
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(phrase)}(?![A-Za-z0-9])", text) is not None


def _canonically_resolved(left: Mapping[str, Any], right: Mapping[str, Any], pair: PairIdentity) -> bool:
    if _short(left.get("superseded_by")) == pair.right_id or _short(right.get("superseded_by")) == pair.left_id:
        return True
    relationships = _relationships(left.get("relationships")) + _relationships(right.get("relationships"))
    return any(
        edge["type"] in {"corrects", "contradicts"}
        and ((edge["target"] == pair.left_id) or (edge["target"] == pair.right_id))
        for edge in relationships
    )


def _similarity_score(scores: Mapping[tuple[str, str], float] | None, pair: PairIdentity) -> float | None:
    if scores is None:
        return None
    score = scores.get(pair.as_tuple())
    if score is None:
        score = scores.get((pair.right_id, pair.left_id))
    if score is None:
        return None
    if not math.isfinite(score):
        raise ValueError("similarity scores must be finite")
    return float(score)


def _relationships(value: Any) -> list[dict[str, str]]:
    edges: list[dict[str, str]] = []
    if value is None:
        return edges
    if isinstance(value, Mapping):
        for relation_type, targets in value.items():
            if isinstance(relation_type, str) and isinstance(targets, (list, tuple, set)):
                for target in targets:
                    if isinstance(target, str):
                        edge = {"type": _short(relation_type), "target": _id(target)}
                        if edge["type"] and edge["target"]:
                            edges.append(edge)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            if isinstance(item, Mapping):
                relation_type = item.get("type", item.get("relation"))
                target = item.get("target", item.get("id", item.get("lesson_id")))
                if isinstance(relation_type, str) and isinstance(target, str):
                    edge = {"type": _short(relation_type), "target": _id(target)}
                    if edge["type"] and edge["target"]:
                        edges.append(edge)
    return sorted(edges, key=lambda edge: (edge["type"], edge["target"]))


def _candidate_sort_key(candidate: ContradictionCandidate) -> tuple[float, str, str, tuple[str, ...]]:
    score = candidate.similarity_score if candidate.similarity_score is not None else -1.0
    return (-score, candidate.left_id, candidate.right_id, candidate.reasons)


def _value(value: Any) -> str:
    return "" if value is None else str(value)


def _display(value: Any) -> str:
    return " ".join(unicodedata.normalize("NFC", _value(value)).strip().split())


def _id(value: Any) -> str:
    return unicodedata.normalize("NFC", _value(value)).strip()


def _short(value: Any) -> str:
    return _display(value).casefold()


def _short_text(value: Any) -> str:
    return " ".join(_text(value).split()).casefold()


def _text(value: Any) -> str:
    text = unicodedata.normalize("NFC", _value(value)).replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def _tags(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return sorted({_short(tag) for tag in value if _short(tag)})


def _date(value: Any) -> str:
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        try:
            return _short(isoformat()[:10])
        except (TypeError, ValueError):
            pass
    return _short(value)
