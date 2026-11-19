"""Mock AI engine - realistic analysis without any external API.

WHAT THIS FILE DOES
    Reads the document text with deterministic rules + regular expressions
    and returns exactly the same JSON shape as the real Gemini engine:
    summary, category, key entities, priority, action items, observations.

WHY IT EXISTS
    1. The project can be demonstrated with zero API keys.
    2. CI/CD tests run fast and never cost money.
    3. It is a honest simulation - it never claims to be Gemini.

HOW IT CONNECTS
    mock_provider.py wraps this engine as the Mock entry of the
    services/ai/ provider chain (selected when MOCK_AI=true); the other
    providers in that package talk to real APIs.

INTERVIEW NOTE
    "Mock mode uses keyword classification and regex entity extraction, so
     the results are deterministic and testable, while the AI service
     interface stays identical to production."
"""
import re
import time
from datetime import date

from app.core.constants import CATEGORY_KEYWORDS, DOCUMENT_CATEGORIES

# Short, capped delay so the UI shows its processing animation.
MOCK_DELAY_SECONDS = 1.2

# --- Regular expressions used for entity extraction --------------------
_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("Email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("URL", re.compile(r"https?://[^\s,;)]+")),
    (
        "Money",
        re.compile(r"(?:\$|₹|€|USD\s|EUR\s|INR\s)\s?\d[\d,]*(?:\.\d{1,2})?|\b\d[\d,]*\s?(?:USD|EUR|INR)\b"),
    ),
    (
        "Date",
        re.compile(
            r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"
            r"|\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b"
            r"|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b"
        ),
    ),
    ("Phone", re.compile(r"\+\d{1,3}[\s-]?\d{2,4}[\s-]?\d{3,4}[\s-]?\d{3,4}\b")),
    (
        "Organization",
        re.compile(
            r"\b[A-Z][\w&'’-]+(?:\s+[A-Z][\w&'’-]+){0,4}\s+"
            r"(?:Inc|LLC|Ltd|Limited|Corp|Corporation|Technologies|Solutions|Systems|"
            r"Group|Bank|University|Institute|Partners|Industries|Labs)\b"
        ),
    ),
    ("Reference Number", re.compile(r"\b[A-Z]{2,6}-\d{2,}(?:-\d{1,4})?\b|\bINV[- ]?\d{3,}\b")),
    ("Person", re.compile(r"\b(?:Mr|Ms|Mrs|Dr)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b")),
]

_ACTION_VERBS = re.compile(
    r"\b(must|should|needs? to|need to|please|kindly|action required|ensure|"
    r"require[ds]?|we will|you are requested|kindly note|todo|to do)\b",
    re.IGNORECASE,
)

_DEADLINE_WORDS = re.compile(
    r"\b(urgent|asap|immediate|deadline|due by|overdue|expir\w*|within \d+ days?|"
    r"end of (?:day|week|month)|time[- ]sensitive|final notice|by \d{1,2})\b",
    re.IGNORECASE,
)

_LOW_WORDS = re.compile(
    r"\b(for your information|fyi|optional|informational|when convenient|no rush|"
    r"newsletter|announcement|reference only|update only)\b",
    re.IGNORECASE,
)


def generate_analysis(text: str) -> dict:
    """Return a validated-shaped analysis dictionary for the given text."""
    time.sleep(MOCK_DELAY_SECONDS)  # makes the frontend animation meaningful

    cleaned = text.strip()
    lower = cleaned.lower()
    sentences = _split_sentences(cleaned)

    category = _detect_category(lower)
    priority, priority_reason = _detect_priority(lower, sentences)
    entities = _extract_entities(cleaned)
    action_items = _build_action_items(sentences, priority)
    observations = _build_observations(cleaned, sentences, entities, lower)

    return {
        "summary": _build_summary(sentences, cleaned),
        "category": category,
        "key_entities": entities,
        "priority": priority,
        "priority_reason": priority_reason,
        "action_items": action_items,
        "observations": observations,
    }


# --- Text helpers ------------------------------------------------------
def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n{2,}", text)
    return [part.strip() for part in parts if part and len(part.strip()) > 2]


def _build_summary(sentences: list[str], text: str) -> str:
    """Lead with the opening of the document and close with its ending."""
    if not sentences:
        return text[:300].strip()

    chosen = sentences[:2]
    if len(sentences) > 3 and sentences[-1] not in chosen:
        chosen.append(sentences[-1])
    summary = " ".join(chosen)
    if len(summary) > 600:
        summary = summary[:597].rstrip() + "..."
    return summary


def _detect_category(lower_text: str) -> str:
    """Score every category by keyword hits and keep the best one."""
    best_category, best_score = "General Document", 0
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(lower_text.count(keyword) for keyword in keywords)
        if score > best_score:
            best_category, best_score = category, score
    return best_category if best_score > 0 else "General Document"


def _detect_priority(lower_text: str, sentences: list[str]) -> tuple[str, str]:
    high_hits = len(_DEADLINE_WORDS.findall(lower_text))
    low_hits = len(_LOW_WORDS.findall(lower_text))

    if high_hits > 0:
        return (
            "High",
            f"The document contains time-sensitive language ({high_hits} urgent term(s)) "
            "such as deadlines or escalation wording.",
        )
    if low_hits > 0 and high_hits == 0:
        return (
            "Low",
            "The content reads as informational material without an immediate obligation.",
        )
    return (
        "Medium",
        "No explicit urgency or deadline was detected, but the document contains "
        "items that require follow-up.",
    )


def _extract_entities(text: str) -> list[dict]:
    """Regex based extraction - facts, never invented."""
    entities: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for entity_type, pattern in _PATTERNS:
        for match in pattern.findall(text):
            value = str(match).strip().rstrip(".,;:")
            if len(value) < 3 or len(value) > 300:
                continue
            key = (entity_type, value.lower())
            if key in seen:
                continue
            seen.add(key)
            entities.append({"type": entity_type, "value": value})
            if len(entities) >= 40:  # keep the payload readable
                return entities
    return entities


def _find_date_in(sentence: str) -> str | None:
    """Return an ISO date found in the sentence, or None (never guessed)."""
    iso_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", sentence)
    if iso_match:
        try:
            return date.fromisoformat(iso_match.group(1)).isoformat()
        except ValueError:
            pass

    for pattern in (r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", r"\b(\d{1,2})-(\d{1,2})-(\d{4})\b"):
        match = re.search(pattern, sentence)
        if not match:
            continue
        day, month, year = (int(part) for part in match.groups())
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            continue
    return None


def _build_action_items(sentences: list[str], document_priority: str) -> list[dict]:
    """Turn sentences that contain an instruction into suggested tasks."""
    items: list[dict] = []
    for sentence in sentences:
        if not _ACTION_VERBS.search(sentence):
            continue
        items.append(
            {
                "title": _sentence_to_title(sentence),
                "description": sentence,
                "priority": document_priority,
                "due_date": _find_date_in(sentence),
            }
        )
        if len(items) >= 5:
            break

    if items:
        return items

    # Nothing imperative found: offer clearly labelled review suggestions
    # based on the document itself rather than inventing facts.
    return [
        {
            "title": "Review document and confirm next steps",
            "description": "Read the document and confirm the required follow-up actions.",
            "priority": document_priority,
            "due_date": None,
        },
        {
            "title": "Share findings with the relevant stakeholders",
            "description": "Summarise the key points of this document for the team.",
            "priority": "Medium",
            "due_date": None,
        },
    ]


def _sentence_to_title(sentence: str) -> str:
    """First ~10 words of the sentence, trimmed and capitalised."""
    words = sentence.strip().split()
    title = " ".join(words[:10])
    if len(words) > 10:
        title += "..."
    title = title.rstrip(".!?;,")
    return title[:1].upper() + title[1:] if title else "Follow-up action"


def _build_observations(
    text: str, sentences: list[str], entities: list[dict], lower_text: str
) -> list[str]:
    """Facts about the document that do not fit the other fields."""
    observations: list[str] = []
    word_count = len(text.split())
    observations.append(f"The document contains approximately {word_count} words.")

    if _DEADLINE_WORDS.search(lower_text):
        observations.append("Deadline or urgency wording was detected in the content.")
    if any(entity["type"] == "Money" for entity in entities):
        observations.append("Monetary values appear in the document.")
    if any(entity["type"] == "Date" for entity in entities):
        observations.append("Explicit dates were found and are listed under key entities.")
    if any(entity["type"] == "Email" for entity in entities):
        observations.append("Contact email address(es) are present in the document.")
    if word_count < 60:
        observations.append("The document is short; consider adding more context when reviewing it.")
    if len(sentences) > 0 and len(sentences) < 4:
        observations.append("The content is brief and may be an excerpt rather than a full document.")

    # Only mention categories the text actually triggered.
    for category in DOCUMENT_CATEGORIES[:3]:
        if category.lower() in lower_text:
            observations.append(f"The phrase '{category}' appears in the document.")

    return observations[:8]


# --- Chat with document ------------------------------------------------
_QUESTION_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "what", "who", "when",
    "where", "why", "how", "does", "do", "did", "in", "on", "at", "of",
    "to", "for", "and", "or", "this", "that", "it", "its", "be", "by",
    "document", "doc", "please", "tell", "me", "about", "any", "from",
}


def answer_question(document_text: str, question: str) -> str:
    """Mock-mode chat: extract the most relevant sentences from the document.

    This is deliberately simple and honest - it quotes the document instead
    of pretending to understand it, and clearly says when nothing matches.
    """
    time.sleep(min(MOCK_DELAY_SECONDS, 0.8))

    sentences = _split_sentences(document_text)
    if not sentences:
        return "This document has no readable text to answer questions about."

    question_words = {
        word for word in re.findall(r"[a-z0-9]+", question.lower())
        if len(word) > 2 and word not in _QUESTION_STOPWORDS
    }

    scored = []
    for sentence in sentences:
        sentence_words = set(re.findall(r"[a-z0-9]+", sentence.lower()))
        overlap = len(question_words & sentence_words)
        # Small bonus when the whole question phrase appears verbatim.
        if question.strip().lower() in sentence.lower():
            overlap += 5
        scored.append((overlap, sentence))

    scored.sort(key=lambda pair: pair[0], reverse=True)

    best_score, best_sentence = scored[0]
    if best_score == 0:
        return (
            "I could not find information related to that question in this document. "
            "Try asking about names, dates, amounts, deadlines or action items mentioned in the text."
        )

    answer_parts = [best_sentence]
    # Add the next-best sentence too when it is nearly as relevant.
    if len(scored) > 1 and scored[1][0] >= max(best_score - 1, 1):
        answer_parts.append(scored[1][1])

    return " ".join(answer_parts)[:1500]
