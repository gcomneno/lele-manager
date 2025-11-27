from __future__ import annotations

from typing import List

import pytest

from lele_manager.model import Lesson
from lele_manager.ml.text_ml import LessonSimilarityIndex, train_topic_classifier

def _make_lessons_for_ml() -> List[Lesson]:
    return [
        Lesson.new(
            source="chatgpt",
            topic="python",
            importance=4,
            text="Uso di pytest e layout src in progetti Python.",
            tags=["python", "pytest"],
        ),
        Lesson.new(
            source="chatgpt",
            topic="ml",
            importance=5,
            text="Introduzione a TF-IDF e modelli di classificazione testuale.",
            tags=["ml", "nlp"],
        ),
        Lesson.new(
            source="book",
            topic="ml",
            importance=3,
            text="Concetti base di machine learning supervisionato.",
            tags=["ml"],
        ),
    ]

def test_train_topic_classifier_predicts_training_topics() -> None:
    lessons = _make_lessons_for_ml()
    classifier = train_topic_classifier(lessons)

    texts = [lesson.text for lesson in lessons]
    true_topics = [lesson.topic for lesson in lessons]

    predicted = list(classifier.predict(texts))

    # Non chiediamo perfezione, ma vogliamo che i topic siano coerenti
    assert set(predicted) <= set(true_topics)
    assert len(predicted) == len(true_topics)

def test_lesson_similarity_index_returns_most_similar() -> None:
    lessons = _make_lessons_for_ml()
    index = LessonSimilarityIndex.from_lessons(lessons)

    # Query chiaramente più simile alla lesson con topic python
    query = "pytest in un progetto Python"

    results = index.most_similar(query_text=query, top_k=2)

    assert len(results) == 2

    top_id, top_score = results[0]
    assert top_score >= 0.0

    python_lesson = next(lesson for lesson in lessons if lesson.topic == "python")
    assert top_id == python_lesson.id

def test_train_topic_classifier_requires_two_topics() -> None:
    lesson = Lesson.new(
        source="chatgpt",
        topic="python",
        importance=4,
        text="Solo un topic non basta.",
        tags=["python"],
    )

    with pytest.raises(ValueError):
        train_topic_classifier([lesson])
