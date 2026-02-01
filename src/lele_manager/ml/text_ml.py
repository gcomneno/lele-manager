from dataclasses import dataclass
from typing import List, Sequence, Tuple

import numpy as np
from scipy.sparse import csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.pipeline import Pipeline

from lele_manager.model import Lesson


def _collect_text_and_labels(lessons: Sequence[Lesson]) -> Tuple[List[str], List[str]]:
    """Estrae (testo, topic) dalle lesson con topic non vuoto."""
    texts: List[str] = []
    labels: List[str] = []
    for lesson in lessons:
        if lesson.topic and lesson.text.strip():
            texts.append(lesson.text)
            labels.append(lesson.topic)
    return texts, labels


def train_topic_classifier(lessons: Sequence[Lesson]) -> Pipeline:
    """
    Allena un classificatore di topic:
    TF-IDF (unigrammi+bigrammi) + LogisticRegression.

    Richiede:
    - almeno 2 lesson con topic non vuoto,
    - almeno 2 topic distinti.
    """
    texts, labels = _collect_text_and_labels(lessons)

    if len(texts) < 2:
        raise ValueError("Servono almeno 2 lesson con topic non vuoto per addestrare il classificatore.")

    if len(set(labels)) < 2:
        raise ValueError("Servono almeno 2 topic distinti per addestrare il classificatore.")

    pipeline = Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    ngram_range=(1, 2),
                    min_df=1,
                ),
            ),
            (
                "logreg",
                LogisticRegression(
                ),
            ),
        ],
    )

    pipeline.fit(texts, labels)
    return pipeline


@dataclass
class LessonSimilarityIndex:
    """
    Indice di similarità tra lesson basato su TF-IDF + coseno.

    - vectorizer: TfidfVectorizer addestrato sui testi delle lesson
    - matrix: matrice TF-IDF (n_lesson x n_feature)
    - lesson_ids: ID delle lesson in ordine di riga
    """

    vectorizer: TfidfVectorizer
    matrix: csr_matrix
    lesson_ids: List[str]

    @classmethod
    def from_lessons(cls, lessons: Sequence[Lesson]) -> "LessonSimilarityIndex":
        texts: List[str] = []
        ids: List[str] = []

        for lesson in lessons:
            if not lesson.text.strip():
                continue
            texts.append(lesson.text)
            ids.append(lesson.id)

        if not texts:
            raise ValueError("Nessuna lesson con testo non vuoto da indicizzare.")

        vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            min_df=1,
        )
        matrix = vectorizer.fit_transform(texts)

        return cls(vectorizer=vectorizer, matrix=matrix, lesson_ids=ids)

    def most_similar(self, query_text: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """
        Ritorna una lista di (lesson_id, score) ordinate per similarità decrescente.

        - query_text: testo della query
        - top_k: numero massimo di risultati
        """
        if not query_text.strip():
            raise ValueError("query_text vuoto, impossibile calcolare la similarità.")

        if self.matrix.shape[0] == 0:
            return []

        query_vec = self.vectorizer.transform([query_text])
        scores = cosine_similarity(query_vec, self.matrix)[0]

        top_k = max(1, min(top_k, len(self.lesson_ids)))
        indices = np.argsort(scores)[::-1][:top_k]

        results: List[Tuple[str, float]] = []
        for idx in indices:
            row_index = int(idx)
            lesson_id = self.lesson_ids[row_index]
            score = float(scores[row_index])
            results.append((lesson_id, score))
        return results
