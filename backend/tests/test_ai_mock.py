"""AI engine tests: Mock mode output, validation and error handling."""
import pytest

from app.schemas.ai import AIAnalysis, parse_ai_response
from app.services import ai_service, mock_ai
from app.utils.errors import AppError


def test_mock_analysis_matches_the_strict_schema(sample_text):
    """Whatever the mock returns must pass Pydantic validation."""
    payload = mock_ai.generate_analysis(sample_text)
    analysis = AIAnalysis.model_validate(payload)

    assert analysis.summary
    assert analysis.category
    assert analysis.priority in ("High", "Medium", "Low")
    assert analysis.priority_reason
    assert isinstance(analysis.action_items, list)
    assert isinstance(analysis.observations, list)


def test_mock_marks_urgent_documents_as_high_priority():
    payload = mock_ai.generate_analysis(
        "URGENT: this request must be completed immediately. "
        "The deadline is 2026-12-01 and any delay will trigger an escalation."
    )
    assert payload["priority"] == "High"
    assert "urgent" in payload["priority_reason"].lower() or "deadline" in payload["priority_reason"].lower()


def test_mock_marks_informational_documents_as_low_priority():
    payload = mock_ai.generate_analysis(
        "For your information, this is an optional announcement for reference only. "
        "Please read it when convenient."
    )
    assert payload["priority"] == "Low"


def test_mock_detects_meeting_notes_category():
    payload = mock_ai.generate_analysis(
        "Minutes of Meeting. Agenda: sprint planning. Attendees: Priya, Ravi. "
        "Meeting held on 2026-11-10. Action points: update the tracker."
    )
    assert payload["category"] == "Meeting Notes"


def test_mock_extracts_real_entities_only(sample_text):
    payload = mock_ai.generate_analysis(sample_text)
    entity_types = {entity["type"] for entity in payload["key_entities"]}

    # Facts that are literally present in the source text:
    assert "Email" in entity_types        # proposals@acmetech.com
    assert "Date" in entity_types         # 2026-12-01
    assert "Money" in entity_types        # USD 45,000
    values = " ".join(entity["value"] for entity in payload["key_entities"])
    assert "proposals@acmetech.com" in values
    assert "PROJ-2026-118" in values


def test_mock_never_invents_dates_for_action_items():
    payload = mock_ai.generate_analysis(
        "Please review the attached notes and share your feedback with the team."
    )
    # No explicit date exists in the text -> due_date must be null.
    assert all(item["due_date"] is None for item in payload["action_items"])


def test_analyze_text_returns_mock_provider(sample_text):
    analysis, provider, notice = ai_service.analyze_text(sample_text)
    assert provider == "mock"
    assert notice is None  # no fallback happened in mock mode
    assert isinstance(analysis, AIAnalysis)
    assert analysis.action_items


def test_ai_service_rejects_malformed_response():
    with pytest.raises(AppError) as error:
        ai_service._validate({"summary": "", "category": "X", "priority": "Impossible"})
    assert error.value.status_code == 502


def test_ai_service_rejects_non_object_payload():
    with pytest.raises(AppError) as error:
        ai_service._validate(["not", "an", "object"])
    assert error.value.status_code == 502


def test_priority_aliases_are_normalised():
    analysis = parse_ai_response(
        {
            "summary": "A summary of the document.",
            "category": "Unknown Category",
            "priority": "urgent",
            "key_entities": [],
            "action_items": [],
            "observations": [],
        }
    )
    assert analysis.priority == "High"
    # Unknown categories fall back so the frontend filters stay finite.
    assert analysis.category == "General Document"


def test_action_item_dates_are_parsed_when_explicit():
    analysis = parse_ai_response(
        {
            "summary": "A summary of the document.",
            "category": "Business Proposal",
            "priority": "High",
            "action_items": [
                {"title": "Send the contract", "due_date": "2026-12-01"},
                {"title": "Call the client", "due_date": None},
            ],
        }
    )
    assert analysis.action_items[0].due_date.isoformat() == "2026-12-01"
    assert analysis.action_items[1].due_date is None


def test_ensure_text_length_rejects_empty_input():
    with pytest.raises(AppError) as error:
        ai_service.ensure_text_length("    ")
    assert error.value.status_code == 503
