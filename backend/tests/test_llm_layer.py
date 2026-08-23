"""LLM layer tests: rule-based fallback + provider wiring via local mock endpoint."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.core.config import settings
from app.services.llm.client import OpenAICompatibleClient, get_llm_client


class _MockOpenAI(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        # Verify evidence actually reached the prompt.
        user_msg = body["messages"][1]["content"]
        evidence = json.loads(user_msg)
        assert "transaction" in evidence and "candidate_actions" in evidence
        resp = {
            "choices": [{"message": {"content": "MOCK-LLM: payment link selected due to strong customer history."}}],
        }
        data = json.dumps(resp).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):  # silence
        pass


@pytest.fixture(scope="module")
def mock_llm_url():
    server = HTTPServer(("127.0.0.1", 0), _MockOpenAI)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


def test_no_provider_returns_none(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "none")
    assert get_llm_client() is None


def test_configured_provider_wired_and_explains(mock_llm_url, monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai_compatible")
    monkeypatch.setattr(settings, "LLM_API_KEY", "test-key")
    monkeypatch.setattr(settings, "LLM_MODEL", "test-model")
    monkeypatch.setattr(settings, "LLM_BASE_URL", mock_llm_url)

    client = get_llm_client()
    assert isinstance(client, OpenAICompatibleClient)
    out = client.explain_decision({
        "transaction": {"payment_id": 1},
        "candidate_actions": [{"action_type": "RETRY_NOW"}],
    })
    assert out.startswith("MOCK-LLM:")


def test_unknown_provider_falls_back_to_none(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "doesnotexist")
    assert get_llm_client() is None
