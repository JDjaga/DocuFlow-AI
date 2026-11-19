"""Chat-with-document tests: answers, validation and user isolation."""
from fastapi.testclient import TestClient


def _analyze(client: TestClient, headers: dict, text: str) -> dict:
    response = client.post("/api/documents/analyze", data={"text": text}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["document"]


def test_chat_returns_answer_from_document_text(client, register_user, sample_text):
    headers = register_user(client)["headers"]
    document = _analyze(client, headers, sample_text)

    response = client.post(
        f"/api/documents/{document['id']}/chat",
        json={"question": "What is the deadline for submitting the bid?"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["document_id"] == document["id"]
    assert body["provider"] == "mock"
    assert "2026-12-01" in body["answer"]


def test_chat_unknown_question_gets_honest_fallback(client, register_user, sample_text):
    headers = register_user(client)["headers"]
    document = _analyze(client, headers, sample_text)

    response = client.post(
        f"/api/documents/{document['id']}/chat",
        json={"question": "What is the weather in Paris tomorrow?"},
        headers=headers,
    )
    assert response.status_code == 200
    assert "could not find" in response.json()["answer"].lower()


def test_chat_question_too_short_rejected(client, register_user, sample_text):
    headers = register_user(client)["headers"]
    document = _analyze(client, headers, sample_text)

    response = client.post(
        f"/api/documents/{document['id']}/chat",
        json={"question": "hi"},
        headers=headers,
    )
    assert response.status_code == 422


def test_chat_requires_authentication(client):
    response = client.post("/api/documents/1/chat", json={"question": "summarize this"})
    assert response.status_code == 401


def test_chat_cannot_access_other_users_document(client, register_user, sample_text):
    owner = register_user(client, email="owner@example.com")["headers"]
    intruder = register_user(client, email="intruder@example.com")["headers"]
    document = _analyze(client, owner, sample_text)

    response = client.post(
        f"/api/documents/{document['id']}/chat",
        json={"question": "What is the budget?"},
        headers=intruder,
    )
    # 404 - the resource's existence is not even revealed.
    assert response.status_code == 404
