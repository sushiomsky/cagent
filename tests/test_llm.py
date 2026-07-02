import json
import urllib.error

from cagent.llm import ChatMessage, LLMError, OpenAICompatibleClient


def test_complete_returns_message_text(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        return FakeResponse({"choices": [{"message": {"content": "hello"}}]})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = OpenAICompatibleClient(base_url="http://local/v1", model="demo", timeout_seconds=7)

    text = client.complete(messages=[ChatMessage("user", "hi")], temperature=0.1, max_tokens=20)

    assert text == "hello"
    assert calls[0][1] == 7
    assert calls[0][0].full_url == "http://local/v1/chat/completions"


def test_list_models_returns_ids(monkeypatch):
    def fake_urlopen(request, timeout):
        return FakeResponse({"data": [{"id": "a"}, {"id": "b"}, {"name": "ignored"}]})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = OpenAICompatibleClient(base_url="http://local/v1", model="demo")

    assert client.list_models() == ["a", "b"]


def test_request_retries_temporary_url_error(monkeypatch):
    calls = {"count": 0}

    def fake_urlopen(request, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            raise urllib.error.URLError("temporary")
        return FakeResponse({"data": []})

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = OpenAICompatibleClient(
        base_url="http://local/v1",
        model="demo",
        retries=1,
        retry_backoff_seconds=0,
    )

    assert client.list_models() == []
    assert calls["count"] == 2


def test_request_stops_after_retry_budget(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = OpenAICompatibleClient(
        base_url="http://local/v1",
        model="demo",
        retries=1,
        retry_backoff_seconds=0,
    )

    try:
        client.list_models()
    except LLMError as exc:
        assert "Could not reach model endpoint" in str(exc)
    else:
        raise AssertionError("expected LLMError")


def test_invalid_json_raises_llm_error(monkeypatch):
    def fake_urlopen(request, timeout):
        return FakeRawResponse("not json")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = OpenAICompatibleClient(base_url="http://local/v1", model="demo")

    try:
        client.list_models()
    except LLMError as exc:
        assert "invalid JSON" in str(exc)
    else:
        raise AssertionError("expected LLMError")


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class FakeRawResponse:
    def __init__(self, text):
        self.text = text

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.text.encode("utf-8")
