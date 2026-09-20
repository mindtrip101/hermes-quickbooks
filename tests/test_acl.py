import pytest

from hermes_qbo.service import ConnectorError


def test_engineering_has_no_access(fake):
    connector, backend, _ = fake
    result = connector.dispatch(agent_id="buzz-engineering", tool="qbo_health", arguments={})
    assert result["ok"] is False
    assert "read_denied" in result["errors"] or "tenant_denied" in result["errors"]
    assert backend.post_count == 0


def test_unknown_agent_denied(fake):
    connector, _, _ = fake
    result = connector.dispatch(agent_id="stranger", tool="qbo_get_company_info", arguments={})
    assert result["ok"] is False
    assert "unknown_agent" in result["errors"]


def test_office_cannot_read_vendors(fake):
    connector, _, _ = fake
    result = connector.dispatch(agent_id="buzz-office", tool="qbo_search_vendors", arguments={})
    assert result["ok"] is False
    assert "read_denied" in result["errors"]


def test_office_can_search_customers(fake):
    connector, _, _ = fake
    result = connector.dispatch(agent_id="buzz-office", tool="qbo_search_customers", arguments={"query": "Ignore"})
    assert result["ok"] is True
    assert result["data_classification"] == "untrusted_external"


def test_read_agent_cannot_draft(fake):
    connector, backend, _ = fake
    result = connector.dispatch(
        agent_id="buzz-office",
        tool="qbo_create_invoice_draft",
        arguments={"customer_id": "1", "line_amount": 10},
    )
    assert result["ok"] is False
    assert "draft_denied" in result["errors"]
    assert backend.post_count == 0


def test_spoofed_agent_argument_is_ignored(fake):
    connector, _, _ = fake
    result = connector.dispatch(
        agent_id="buzz-engineering",
        tool="qbo_search_customers",
        arguments={"agent_id": "hermes-operator", "tenant_id": "company_a"},
    )
    assert result["ok"] is False


def test_company_a_cannot_use_company_b(fake):
    connector, backend, _ = fake
    result = connector.dispatch(
        agent_id="hermes-operator",
        tool="qbo_get_company_info",
        arguments={"tenant_id": "company_b"},
    )
    assert result["ok"] is False
    assert "tenant_denied" in result["errors"]
    assert not any("realm-b" in str(c.url) for c in backend.calls)


def test_telegram_can_draft_but_not_via_execute(fake):
    connector, backend, _ = fake
    result = connector.dispatch(
        agent_id="hermes-telegram",
        tool="qbo_create_invoice_draft",
        arguments={"customer_id": "1", "line_amount": 25},
    )
    assert result["posted_to_quickbooks"] is False
    assert backend.post_count == 0
    action_id = result["data"]["action"]["id"]
    with pytest.raises(ConnectorError):
        connector.operator_execute(action_id, user="operator")
    assert backend.post_count == 0
