from gemini_ops_agent.mcp_stub import (
    CANNED_PROBLEMS,
    _dql_response,
    find_entity_response,
    generate_dql_response,
    list_problems_response,
)


def test_canned_problems_loaded():
    assert len(CANNED_PROBLEMS) >= 2
    titles = [p.title for p in CANNED_PROBLEMS]
    assert any("checkout-api" in t for t in titles)


def test_list_problems_response_shape():
    payload = list_problems_response()
    assert "problems" in payload
    assert any(p["id"] == "P-2026-0517-001" for p in payload["problems"])


def test_execute_dql_latency_query():
    payload = _dql_response("fetch logs | filter service == \"checkout-api\" | latency p95")
    assert "records" in payload
    assert any(r.get("service") == "checkout-api" for r in payload["records"])


def test_execute_dql_error_query():
    payload = _dql_response("fetch logs | filter level == \"ERROR\"")
    assert "records" in payload
    assert any(r.get("level") == "ERROR" for r in payload["records"])


def test_find_entity_resolves_known_service():
    payload = find_entity_response("checkout-api")
    assert payload["entity_id"].startswith("SERVICE-")


def test_find_entity_unknown_returns_none():
    payload = find_entity_response("unknown-service")
    assert payload["entity_id"] is None


def test_generate_dql_for_latency_question():
    payload = generate_dql_response("show me latency for checkout in the last hour")
    assert payload["dql"].startswith("fetch logs")


def test_generate_dql_default_returns_deployments():
    payload = generate_dql_response("anything else")
    assert "DEPLOYMENT" in payload["dql"]
