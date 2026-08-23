from __future__ import annotations

from copy import deepcopy

import pytest

from lele_manager.core.contradiction_review import (
    AUXILIARY_DECISIONS,
    CONTRADICTION_REVIEW_REASONS,
    PairIdentity,
    generate_contradiction_candidates,
    material_fingerprint,
    validate_auxiliary_decision,
    validate_reason,
)


def _lesson(lesson_id: str, **overrides: object) -> dict[str, object]:
    lesson: dict[str, object] = {
        "id": lesson_id,
        "title": f"Lesson {lesson_id}",
        "topic": "python",
        "source": "guide",
        "date": "2026-08-10",
        "tags": ["testing"],
        "lifecycle": "active",
        "superseded_by": "",
        "relationships": [],
        "text": "Use retry for transient failures.",
    }
    lesson.update(overrides)
    return lesson


def test_pair_identity_is_orientation_independent() -> None:
    assert PairIdentity.from_ids("b", "a") == PairIdentity.from_ids("a", "b")
    assert PairIdentity.from_ids("b", "a").as_tuple() == ("a", "b")


@pytest.mark.parametrize("left,right", [("", "a"), ("a", ""), ("same", "same")])
def test_pair_identity_rejects_invalid_ids(left: str, right: str) -> None:
    with pytest.raises(ValueError, match="two distinct"):
        PairIdentity.from_ids(left, right)


def test_material_fingerprint_stable_under_harmless_representation_normalization() -> None:
    base = _lesson(
        "a",
        text="\nCafe\u0301 body  \r\nsecond line\r\n",
        title="  Same   Title ",
        topic=" Python ",
        source=" NOTE ",
        tags=["Two", "one"],
        relationships=[
            {"type": "corrects", "target": "beta"},
            {"type": "contradicts", "target": "alpha"},
        ],
    )
    same = {
        **base,
        "text": "Café body\nsecond line",
        "title": "same title",
        "topic": "python",
        "source": "note",
        "tags": ["ONE", "two"],
        "relationships": [
            {"target": "alpha", "type": "contradicts"},
            {"target": "beta", "type": "corrects"},
        ],
    }
    assert material_fingerprint(base) == material_fingerprint(same)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("text", "changed body"),
        ("title", "changed title"),
        ("topic", "changed topic"),
        ("source", "changed source"),
        ("date", "2026-08-11"),
        ("tags", ["testing", "new"]),
        ("lifecycle", "review-needed"),
        ("superseded_by", "other/id"),
        ("relationships", [{"type": "corrects", "target": "other/id"}]),
    ],
)
def test_material_fingerprint_changes_for_each_required_field(field: str, value: object) -> None:
    base = _lesson("a")
    changed = {**base, field: value}
    assert material_fingerprint(base) != material_fingerprint(changed)


def test_relationship_normalization_is_deterministic_and_material_by_type_and_target() -> None:
    base = _lesson(
        "a",
        relationships=[
            {"type": "corrects", "target": "b"},
            {"type": "contradicts", "target": "c"},
        ],
    )
    reordered = _lesson(
        "a",
        relationships=[
            {"target": "c", "type": "contradicts"},
            {"target": "b", "type": "corrects"},
        ],
    )
    changed_type = _lesson("a", relationships=[{"type": "contradicts", "target": "b"}])
    changed_target = _lesson("a", relationships=[{"type": "corrects", "target": "d"}])
    assert material_fingerprint(base) == material_fingerprint(reordered)
    assert material_fingerprint(base) != material_fingerprint(changed_type)
    assert material_fingerprint(base) != material_fingerprint(changed_target)


def test_unknown_reason_and_decision_values_fail_explicitly() -> None:
    for reason in CONTRADICTION_REVIEW_REASONS:
        assert validate_reason(reason) == reason
    for decision in AUXILIARY_DECISIONS:
        assert validate_auxiliary_decision(decision) == decision
    with pytest.raises(ValueError, match="unknown contradiction-review reason"):
        validate_reason("same-title")
    with pytest.raises(ValueError, match="unknown contradiction-review decision"):
        validate_auxiliary_decision("corrects")


def test_same_subject_plus_tension_cue_surfaces_candidate() -> None:
    candidates = generate_contradiction_candidates(
        [
            _lesson("a", text="Use retries for transient failures."),
            _lesson("b", text="Do not use retries for transient failures."),
        ]
    )
    assert [(candidate.left_id, candidate.right_id) for candidate in candidates] == [("a", "b")]
    assert candidates[0].same_subject_reasons == ("same-topic", "shared-tags")
    assert candidates[0].tension_reasons == ("negated-shared-phrase",)


@pytest.mark.parametrize(
    "left,right",
    [
        (_lesson("a", topic="python", tags=[]), _lesson("b", topic="python", tags=[], text="Plain text.")),
        (_lesson("a", topic="one", tags=["shared"]), _lesson("b", topic="two", tags=["shared"], text="Plain text.")),
    ],
)
def test_same_subject_alone_does_not_surface(left: dict[str, object], right: dict[str, object]) -> None:
    assert generate_contradiction_candidates([left, right]) == ()


def test_similarity_alone_does_not_surface_and_score_is_metadata_only() -> None:
    candidates = generate_contradiction_candidates(
        [_lesson("a", topic="one", tags=[]), _lesson("b", topic="two", tags=[], text="Plain text.")],
        similarity_scores={("a", "b"): 0.99},
        similarity_threshold=0.8,
    )
    assert candidates == ()
    surfaced = generate_contradiction_candidates(
        [
            _lesson("a", topic="one", tags=[], text="Always cache responses."),
            _lesson("b", topic="two", tags=[], text="Never cache responses."),
        ],
        similarity_scores={("b", "a"): 0.99},
        similarity_threshold=0.8,
    )
    assert surfaced[0].reasons == ("similarity-gate", "opposing-modal-cue")
    assert surfaced[0].similarity_score == 0.99


@pytest.mark.parametrize(
    "left,right",
    [
        (_lesson("a", text="same body"), _lesson("b", text="same body")),
        (_lesson("a", relationships=[{"type": "corrects", "target": "b"}]), _lesson("b")),
        (_lesson("a"), _lesson("b", relationships=[{"type": "contradicts", "target": "a"}])),
        (_lesson("a", superseded_by="b"), _lesson("b")),
        (_lesson("a", lifecycle="deprecated"), _lesson("b")),
        (_lesson("a", lifecycle="archived"), _lesson("b")),
    ],
)
def test_ineligible_pairs_are_excluded(left: dict[str, object], right: dict[str, object]) -> None:
    assert generate_contradiction_candidates([left, right]) == ()


def test_active_and_review_needed_are_allowed() -> None:
    assert generate_contradiction_candidates(
        [
            _lesson("a", lifecycle="active", text="Must pin dependencies."),
            _lesson("b", lifecycle="review-needed", text="Must not pin dependencies."),
        ]
    )


def test_ordering_is_deterministic_under_shuffled_input_and_ties() -> None:
    lessons = [
        _lesson("c", text="Must cache results."),
        _lesson("a", text="Must not cache results."),
        _lesson("b", text="Always retry requests."),
        _lesson("d", text="Never retry requests."),
    ]
    first = generate_contradiction_candidates(lessons)
    second = generate_contradiction_candidates(list(reversed(lessons)))
    assert [(c.left_id, c.right_id) for c in first] == [(c.left_id, c.right_id) for c in second]
    assert [(c.left_id, c.right_id) for c in first] == [("a", "c"), ("b", "d")]


def test_generator_does_not_mutate_inputs_or_files(tmp_path) -> None:  # type: ignore[no-untyped-def]
    marker = tmp_path / "marker.md"
    marker.write_text("before", encoding="utf-8")
    lessons = [_lesson("a", text="Always retry."), _lesson("b", text="Never retry.")]
    before = deepcopy(lessons)
    assert generate_contradiction_candidates(lessons)
    assert lessons == before
    assert marker.read_text(encoding="utf-8") == "before"


def test_zero_and_one_lesson_are_safe() -> None:
    assert generate_contradiction_candidates([]) == ()
    assert generate_contradiction_candidates([_lesson("a")]) == ()


@pytest.mark.parametrize("threshold", [-0.1, 1.1, float("nan")])
def test_invalid_similarity_threshold_fails_explicitly(threshold: float) -> None:
    with pytest.raises(ValueError, match="similarity_threshold"):
        generate_contradiction_candidates([], similarity_threshold=threshold)


@pytest.mark.parametrize("bound", [0, -1])
def test_invalid_analysis_bound_fails_explicitly(bound: int) -> None:
    with pytest.raises(ValueError, match="analysis_bound"):
        generate_contradiction_candidates([], analysis_bound=bound)
