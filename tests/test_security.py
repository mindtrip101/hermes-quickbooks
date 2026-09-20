from hermes_qbo.envelope import INSTRUCTION_BOUNDARY
from hermes_qbo.redaction import redact


def test_prompt_injection_is_data_not_authority(fake):
    connector, backend, _ = fake
    result = connector.dispatch(agent_id="hermes-operator", tool="qbo_get_customer", arguments={"customer_id": "1"})
    assert result["instruction_boundary"] == INSTRUCTION_BOUNDARY
    assert result["data_classification"] == "untrusted_external"
    name = result["data"]["DisplayName"]
    assert "Ignore previous instructions" in name
    denied = connector.dispatch(
        agent_id="buzz-engineering",
        tool="qbo_create_invoice_draft",
        arguments={"customer_id": "1", "line_amount": 1, "description": name},
    )
    assert denied["ok"] is False
    assert backend.post_count == 0


def test_audit_redacts_tokens(fake):
    connector, _, settings = fake
    connector.dispatch(
        agent_id="hermes-operator",
        tool="qbo_search_customers",
        arguments={"query": "x", "access_token": "super-secret-token-value"},
    )
    text = settings.audit_path.read_text()
    assert "super-secret-token-value" not in text
    assert "[redacted]" in text
    assert "refresh-aaa" not in text
    assert "access-aaa" not in text


def test_redact_helper():
    payload = redact({"refresh_token": "abc", "nested": {"client_secret": "zzz"}})
    assert payload["refresh_token"] == "[redacted]"
    assert payload["nested"]["client_secret"] == "[redacted]"
