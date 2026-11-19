"""Task tests: CRUD, status changes, conversion from AI action items."""
from fastapi.testclient import TestClient


def _create_task(client: TestClient, headers: dict, **overrides) -> dict:
    payload = {"title": "Review proposal", "description": "Check scope and budget", "priority": "High"}
    payload.update(overrides)
    response = client.post("/api/tasks", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_manual_task(client, register_user):
    headers = register_user(client)["headers"]
    task = _create_task(client, headers, status="pending", due_date="2026-12-01")

    assert task["title"] == "Review proposal"
    assert task["status"] == "pending"
    assert task["due_date"] == "2026-12-01"
    assert task["assigned_to"] == "Test User"  # defaults to the logged-in user
    assert task["document_id"] is None


def test_create_task_rejects_invalid_status(client, register_user):
    headers = register_user(client)["headers"]
    response = client.post(
        "/api/tasks",
        json={"title": "Bad status", "status": "finished"},
        headers=headers,
    )
    assert response.status_code == 422


def test_list_tasks_returns_counts_and_filters(client, register_user):
    headers = register_user(client)["headers"]
    _create_task(client, headers, title="Pending one", status="pending")
    _create_task(client, headers, title="Done one", status="completed")
    _create_task(client, headers, title="Review one", status="in_review")

    all_tasks = client.get("/api/tasks", headers=headers).json()
    assert all_tasks["total"] == 3
    assert all_tasks["counts"] == {"pending": 1, "in_review": 1, "completed": 1}

    completed = client.get("/api/tasks?status=completed", headers=headers).json()
    assert completed["total"] == 1
    assert completed["items"][0]["title"] == "Done one"

    searched = client.get("/api/tasks?search=Pending", headers=headers).json()
    assert searched["total"] == 1


def test_update_task_status_and_fields(client, register_user):
    headers = register_user(client)["headers"]
    task = _create_task(client, headers)

    updated = client.put(
        f"/api/tasks/{task['id']}",
        json={"status": "in_review", "priority": "Low", "title": "Review proposal v2"},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "in_review"
    assert updated.json()["priority"] == "Low"
    assert updated.json()["title"] == "Review proposal v2"


def test_task_status_transitions(client, register_user):
    """pending -> in_review -> completed -> pending (reopen)."""
    headers = register_user(client)["headers"]
    task_id = _create_task(client, headers)["id"]

    for status in ("in_review", "completed", "pending"):
        response = client.put(f"/api/tasks/{task_id}", json={"status": status}, headers=headers)
        assert response.status_code == 200
        assert response.json()["status"] == status


def test_delete_task(client, register_user):
    headers = register_user(client)["headers"]
    task_id = _create_task(client, headers)["id"]

    assert client.delete(f"/api/tasks/{task_id}", headers=headers).status_code == 200
    assert client.get(f"/api/tasks/{task_id}", headers=headers).status_code == 404
    assert client.delete(f"/api/tasks/{task_id}", headers=headers).status_code == 404


def test_tasks_are_isolated_between_users(client, register_user):
    alice = register_user(client, email="alice@example.com")["headers"]
    bob = register_user(client, email="bob@example.com")["headers"]

    task_id = _create_task(client, alice)["id"]

    assert client.get(f"/api/tasks/{task_id}", headers=bob).status_code == 404
    assert client.put(f"/api/tasks/{task_id}", json={"status": "completed"}, headers=bob).status_code == 404
    assert client.delete(f"/api/tasks/{task_id}", headers=bob).status_code == 404
    assert client.get("/api/tasks", headers=bob).json()["total"] == 0


def test_convert_ai_action_items_into_tasks(client, register_user, sample_text):
    """End-to-end: analyze -> take the AI action items -> create tasks."""
    headers = register_user(client)["headers"]
    analysis = client.post(
        "/api/documents/analyze", data={"text": sample_text, "title": "Proposal"}, headers=headers
    ).json()
    document_id = analysis["document"]["id"]
    action_items = analysis["document"]["action_items"]
    assert action_items, "The mock AI should always suggest at least one action item"

    created = []
    for item in action_items:
        response = client.post(
            "/api/tasks",
            json={
                "title": item["title"],
                "description": item["description"],
                "priority": item["priority"],
                "document_id": document_id,
                "due_date": item["due_date"],
            },
            headers=headers,
        )
        assert response.status_code == 201, response.text
        created.append(response.json())

    assert all(task["document_id"] == document_id for task in created)
    linked = client.get(f"/api/documents/{document_id}", headers=headers).json()
    assert linked["task_count"] == len(created)

    # Converting the same action item twice is rejected (duplicate protection).
    duplicate = client.post(
        "/api/tasks",
        json={"title": action_items[0]["title"], "document_id": document_id},
        headers=headers,
    )
    assert duplicate.status_code == 400
    assert "already exists" in duplicate.json()["detail"]


def test_task_cannot_reference_another_users_document(client, register_user, sample_text):
    alice = register_user(client, email="alice@example.com")["headers"]
    bob = register_user(client, email="bob@example.com")["headers"]

    document_id = client.post(
        "/api/documents/analyze", data={"text": sample_text}, headers=alice
    ).json()["document"]["id"]

    response = client.post(
        "/api/tasks",
        json={"title": "Injected task", "document_id": document_id},
        headers=bob,
    )
    assert response.status_code == 404


def test_deleting_document_keeps_its_tasks(client, register_user, sample_text):
    headers = register_user(client)["headers"]
    analysis = client.post(
        "/api/documents/analyze", data={"text": sample_text}, headers=headers
    ).json()
    document_id = analysis["document"]["id"]

    client.post(
        "/api/tasks",
        json={"title": "Keep me", "document_id": document_id},
        headers=headers,
    )

    assert client.delete(f"/api/documents/{document_id}", headers=headers).status_code == 200

    tasks = client.get("/api/tasks", headers=headers).json()
    assert tasks["total"] == 1  # the task survived...
    assert tasks["items"][0]["document_id"] is None  # ...but is no longer linked
