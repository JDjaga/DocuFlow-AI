"""Health endpoint tests: meaningful status, no secrets leaked."""


def test_health_reports_api_and_database_status(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["application"] == "DocuFlow AI"
    assert body["version"]
    assert body["database"]["status"] == "healthy"
    assert body["uptime_seconds"] >= 0


def test_health_never_exposes_secrets(client):
    response = client.get("/api/health")
    text = response.text.lower()

    assert "secret" not in text
    assert "sqlite:" not in text          # no connection string
    assert "password" not in text
    assert "database" in response.json()  # component status is reported


def test_ai_health_reports_mock_mode_without_a_key(client):
    response = client.get("/api/health/ai")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["provider"] == "mock"
    assert "mock" in body["mode"].lower()
    assert body["api_key_configured"] is False
    assert body["model"] == "-"           # no model name when running locally

    # No key material of any kind may appear.
    assert "sk-" not in response.text
    assert "secret" not in response.text.lower()


def test_ai_health_describes_every_provider_without_secrets(client):
    """Provider availability block: 4 providers, config state only."""
    response = client.get("/api/health/ai")
    body = response.json()

    assert set(body["providers"]) == {"gemini", "openrouter", "ollama", "mock"}
    for name, info in body["providers"].items():
        assert set(info) == {"label", "inference", "configured", "available", "detail", "model"}
        assert isinstance(info["configured"], bool)
        assert info["label"]
        # availability is a real check or an honest "not checked" - never invented
        assert info["available"] in (True, False, None)

    # Mock mode: mock is configured and reachable, cloud providers are not.
    assert body["providers"]["mock"]["configured"] is True
    assert body["providers"]["mock"]["available"] is True
    assert body["providers"]["gemini"]["configured"] is False
    assert body["providers"]["openrouter"]["configured"] is False
    assert body["providers"]["ollama"]["configured"] is False

    assert body["provider"] == "mock"           # active provider
    assert body["priority"] == ["mock"]  # MOCK_AI=true -> mock-only chain
    assert body["fallback_enabled"] is True


def test_ai_health_reports_embedding_and_real_metrics(client):
    response = client.get("/api/health/ai")
    body = response.json()

    # Independent embedding configuration (separate from generation).
    embedding = body["embedding"]
    assert embedding["provider"] == "mock"          # EMBEDDING_PROVIDER=mock in tests
    assert embedding["model"] == "mock-hash-v1"
    assert embedding["dimension"] == 128
    assert embedding["status"] == "configured"
    assert embedding["detail"]

    # Real counters only - present, non-negative, correctly shaped.
    metrics = body["metrics"]
    assert set(metrics) == {
        "requests", "success", "failed", "fallback_events", "avg_response_time_ms",
    }
    for key in ("requests", "success", "failed", "fallback_events"):
        assert isinstance(metrics[key], int)
        assert metrics[key] >= 0
    assert metrics["avg_response_time_ms"] >= 0
    assert isinstance(body["recent_fallbacks"], list)
    for event in body["recent_fallbacks"]:
        assert set(event) == {"at", "operation", "from", "to", "error_category"}

    # Safe fields only - no keys, no connection strings.
    assert "sk-" not in response.text
    assert "sqlite:" not in response.text
    assert "password" not in response.text.lower()


def test_root_returns_app_info(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["tagline"] == "Turn Documents into Decisions."
    assert response.json()["docs"] == "/docs"
