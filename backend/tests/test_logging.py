import json
import logging

from app.core.logging import JsonFormatter, Redactor


def _format(redactor, msg, *args, **extra):
    record = logging.LogRecord("t", logging.INFO, __file__, 1, msg, args, None)
    for key, value in extra.items():
        setattr(record, key, value)
    return JsonFormatter(redactor).format(record)


def test_configured_secrets_are_redacted_everywhere():
    redactor = Redactor(["my-real-api-key-123"])
    line = _format(redactor, "falha com chave %s", "my-real-api-key-123", url="https://x?k=my-real-api-key-123")
    assert "my-real-api-key-123" not in line
    payload = json.loads(line)
    assert payload["msg"] == "falha com chave ***"


def test_credential_patterns_are_redacted_without_known_secret():
    redactor = Redactor()
    line = _format(redactor, "headers apikey: abcdef password=xyz mongodb://user:pw123@host/db")
    assert "abcdef" not in line and "xyz" not in line and "pw123" not in line


def test_secret_like_extra_keys_are_masked():
    line = _format(Redactor(), "x", apikey="abc", headers={"apikey": "abc", "accept": "json"})
    payload = json.loads(line)
    assert payload["apikey"] == "***"
    assert payload["headers"] == {"apikey": "***", "accept": "json"}


def test_request_id_header_is_returned(client):
    response = client.get("/health", headers={"x-request-id": "abc123"})
    assert response.headers["x-request-id"] == "abc123"
