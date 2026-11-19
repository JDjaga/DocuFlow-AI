"""Document tests: analysis, CRUD, filtering and user isolation."""
import io

from fastapi.testclient import TestClient

from tests.conftest import make_pdf


def _analyze_text(client: TestClient, headers: dict, text: str, title: str = "") -> dict:
    response = client.post(
        "/api/documents/analyze",
        data={"text": text, "title": title},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_analyze_pasted_text_returns_structured_result(client, register_user, sample_text):
    headers = register_user(client)["headers"]
    body = _analyze_text(client, headers, sample_text, title="Acme Proposal")

    assert body["ai_provider"] == "mock"
    document = body["document"]
    assert document["title"] == "Acme Proposal"
    assert document["processing_status"] == "completed"
    assert document["summary"]
    assert document["priority"] in ("High", "Medium", "Low")
    assert document["priority_reason"]
    assert isinstance(document["key_entities"], list) and document["key_entities"]
    assert isinstance(document["action_items"], list)
    assert document["extracted_text"].startswith("Business Proposal")
    assert document["created_at"]


def test_analyze_requires_content(client, register_user):
    headers = register_user(client)["headers"]
    response = client.post("/api/documents/analyze", data={"text": "   "}, headers=headers)
    assert response.status_code == 400


def test_analyze_requires_authentication(client):
    response = client.post("/api/documents/analyze", data={"text": "hello world"})
    assert response.status_code == 401


def test_upload_txt_file(client, register_user):
    headers = register_user(client)["headers"]
    content = io.BytesIO(b"Meeting held on 2026-11-10. Attendees: Priya and Ravi. Action: send notes.")
    response = client.post(
        "/api/documents/analyze",
        data={"title": ""},
        files={"file": ("minutes.txt", content, "text/plain")},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    assert response.json()["document"]["original_filename"] == "minutes.txt"


def test_upload_rejects_unsupported_extension(client, register_user):
    headers = register_user(client)["headers"]
    response = client.post(
        "/api/documents/analyze",
        files={"file": ("malware.exe", io.BytesIO(b"MZbinary"), "application/octet-stream")},
        headers=headers,
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_upload_rejects_fake_pdf(client, register_user):
    """A .pdf extension is not enough - the %PDF signature must be present."""
    headers = register_user(client)["headers"]
    response = client.post(
        "/api/documents/analyze",
        files={"file": ("fake.pdf", io.BytesIO(b"this is not a pdf"), "application/pdf")},
        headers=headers,
    )
    assert response.status_code == 400
    assert "signature" in response.json()["detail"]


def test_upload_reads_real_pdf(client, register_user):
    headers = register_user(client)["headers"]
    pdf_bytes = make_pdf("Urgent: budget approval required by 2026-12-01 for project Alpha.")

    response = client.post(
        "/api/documents/analyze",
        files={"file": ("budget.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    document = response.json()["document"]
    assert document["original_filename"] == "budget.pdf"
    assert "budget approval" in document["extracted_text"].lower()


def test_list_search_filter_and_pagination(client, register_user, sample_text):
    headers = register_user(client)["headers"]
    for index in range(3):
        _analyze_text(client, headers, sample_text, title=f"Document {index}")
    _analyze_text(client, headers, sample_text, title="Unique Title")

    page1 = client.get("/api/documents?page=1&page_size=2", headers=headers).json()
    assert page1["total"] == 4
    assert page1["pages"] == 2
    assert len(page1["items"]) == 2

    found = client.get("/api/documents?search=Unique", headers=headers).json()
    assert found["total"] == 1
    assert found["items"][0]["title"] == "Unique Title"

    no_match = client.get("/api/documents?search=nothingmatchesthis", headers=headers).json()
    assert no_match["total"] == 0
    assert no_match["items"] == []

    # Valid categories come back for the filter dropdown.
    assert "General Document" in page1["categories"] or page1["categories"]


def test_priority_filter(client, register_user, sample_text):
    headers = register_user(client)["headers"]
    _analyze_text(client, headers, sample_text)
    first = client.get("/api/documents?page_size=1", headers=headers).json()["items"][0]
    filtered = client.get(f"/api/documents?priority={first['priority']}", headers=headers).json()
    assert filtered["total"] >= 1


def test_get_update_and_delete_document(client, register_user, sample_text):
    headers = register_user(client)["headers"]
    document_id = _analyze_text(client, headers, sample_text)["document"]["id"]

    detail = client.get(f"/api/documents/{document_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["id"] == document_id

    updated = client.put(
        f"/api/documents/{document_id}",
        json={"user_notes": "Reviewed by the delivery team.", "priority": "Low"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["user_notes"] == "Reviewed by the delivery team."
    assert updated.json()["priority"] == "Low"

    deleted = client.delete(f"/api/documents/{document_id}", headers=headers)
    assert deleted.status_code == 200
    assert client.get(f"/api/documents/{document_id}", headers=headers).status_code == 404


def test_documents_are_isolated_between_users(client, register_user, sample_text):
    """Knowing an id must never expose another user's document."""
    alice = register_user(client, email="alice@example.com")["headers"]
    bob = register_user(client, email="bob@example.com")["headers"]

    document_id = _analyze_text(client, alice, sample_text)["document"]["id"]

    # Bob gets 404 (not 403) so he cannot even confirm it exists.
    assert client.get(f"/api/documents/{document_id}", headers=bob).status_code == 404
    assert client.put(f"/api/documents/{document_id}", json={"user_notes": "hack"}, headers=bob).status_code == 404
    assert client.delete(f"/api/documents/{document_id}", headers=bob).status_code == 404

    # Bob's list does not contain Alice's document.
    assert client.get("/api/documents", headers=bob).json()["total"] == 0
    # Alice still has hers.
    assert client.get("/api/documents", headers=alice).json()["total"] == 1


def test_reanalyze_updates_same_document(client, register_user, sample_text):
    """Re-analysis must refresh the row instead of creating a duplicate."""
    headers = register_user(client)["headers"]
    document_id = _analyze_text(client, headers, sample_text)["document"]["id"]

    response = client.post(
        "/api/documents/analyze",
        data={"text": sample_text + " Additional note about the timeline.", "document_id": str(document_id)},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    assert response.json()["document"]["id"] == document_id
    assert client.get("/api/documents", headers=headers).json()["total"] == 1


# --- Document types: task vs general ---------------------------------
def test_general_document_has_no_action_items(client, register_user, sample_text):
    """General documents get analysis + chat, but never workflow tasks."""
    headers = register_user(client)["headers"]
    body = _analyze_text(client, headers, sample_text)
    # _analyze_text doesn't send document_type -> defaults to "task"
    assert body["document"]["document_type"] == "task"
    assert body["document"]["action_items"], "task docs keep AI action items"

    response = client.post(
        "/api/documents/analyze",
        data={"text": sample_text, "document_type": "general"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    document = response.json()["document"]
    assert document["document_type"] == "general"
    assert document["action_items"] == []
    # ...but the rest of the analysis is still there
    assert document["summary"]
    assert document["key_entities"]
    assert document["category"]


def test_general_document_still_supports_chat(client, register_user, sample_text):
    headers = register_user(client)["headers"]
    response = client.post(
        "/api/documents/analyze",
        data={"text": sample_text, "document_type": "general"},
        headers=headers,
    )
    doc_id = response.json()["document"]["id"]

    chat = client.post(
        f"/api/documents/{doc_id}/chat",
        json={"question": "What is the deadline?"},
        headers=headers,
    )
    assert chat.status_code == 200
    assert "2026-12-01" in chat.json()["answer"]


def test_invalid_document_type_rejected(client, register_user, sample_text):
    headers = register_user(client)["headers"]
    response = client.post(
        "/api/documents/analyze",
        data={"text": sample_text, "document_type": "banana"},
        headers=headers,
    )
    assert response.status_code == 400


def test_document_type_can_be_updated(client, register_user, sample_text):
    headers = register_user(client)["headers"]
    body = _analyze_text(client, headers, sample_text)
    doc_id = body["document"]["id"]

    response = client.put(
        f"/api/documents/{doc_id}",
        json={"document_type": "general"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["document_type"] == "general"

    # Invalid value rejected
    response = client.put(
        f"/api/documents/{doc_id}",
        json={"document_type": "nope"},
        headers=headers,
    )
    assert response.status_code == 400
