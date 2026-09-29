"""
Retrieval over free-text tracker context (currently: day notes).

Structured data (check-ins, streaks, weekly rates) is read directly through
TrackerAnalyticsService; only free text needs ranking. A tracker has at most
one note per day (365 at most), so lexical scoring is enough today.
NoteRetriever is the extension point for an embedding-based implementation
(for example pgvector) if notes, AI conversation history or other long-form
context grow to the point where keyword matching misses too much.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Protocol

_WORD = re.compile(r"[a-z0-9']+")
_STOPWORDS = frozenset(
    "a an and are as at be but by did do for from had has have i in is it its me my no not of on or so "
    "that the this to was were what when why with you your about been how day days".split()
)


@dataclass(frozen=True)
class NoteDocument:
    day_index: int
    date: date
    text: str


@dataclass(frozen=True)
class NoteMatch:
    document: NoteDocument
    score: float


class NoteRetriever(Protocol):
    def search(self, query: str, documents: list[NoteDocument], limit: int) -> list[NoteMatch]: ...


def _terms(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if len(w) > 2 and w not in _STOPWORDS]


class KeywordNoteRetriever:
    """Scores notes by query-term overlap, counting prefix matches (tired ~ tiredness) at half weight."""

    def search(self, query: str, documents: list[NoteDocument], limit: int) -> list[NoteMatch]:
        query_terms = set(_terms(query))
        if not query_terms:
            return []
        matches = []
        for doc in documents:
            words = _terms(doc.text)
            score = 0.0
            for term in query_terms:
                if term in words:
                    score += 1.0
                elif any(w.startswith(term[:5]) or term.startswith(w[:5]) for w in words if len(w) >= 4):
                    score += 0.5
            if score:
                matches.append(NoteMatch(doc, score / len(query_terms)))
        matches.sort(key=lambda m: (-m.score, -m.document.day_index))
        return matches[:limit]
