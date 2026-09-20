import pytest

from hermes_qbo.service import ConnectorError


def test_draft_does_not_post(fake):
    connector, backend, _ = fake
    result = connector.dispatch(
        agent_id="hermes-operator",
        tool="qbo_create_invoice_draft",
        arguments={"customer_id": "1", "line_amount": 99.5, "description": "test"},
    )
    assert result["posted_to_quickbooks"] is False
    assert "has not been posted" in result["data"]["warning"]
    assert backend.post_count == 0
    assert connector.approvals.get(result["data"]["action"]["id"])["status"] == "pending"


def test_agent_cannot_approve_own_request(fake):
    connector, backend, _ = fake
    staged = connector.dispatch(
        agent_id="hermes-operator",
        tool="qbo_create_invoice_draft",
        arguments={"customer_id": "1", "line_amount": 10},
    )
    action_id = staged["data"]["action"]["id"]
    with pytest.raises(Exception):
        connector.operator_decide(action_id, decision="approved", user="hermes-operator")
    assert connector.approvals.get(action_id)["status"] == "pending"
    assert backend.post_count == 0


def test_operator_approve_without_execute_still_unposted(fake):
    connector, backend, _ = fake
    staged = connector.dispatch(
        agent_id="hermes-operator",
        tool="qbo_create_invoice_draft",
        arguments={"customer_id": "1", "line_amount": 10},
    )
    action_id = staged["data"]["action"]["id"]
    decided = connector.operator_decide(action_id, decision="approved", user="operator")
    assert decided["status"] == "approved"
    assert backend.post_count == 0


def test_execute_posts_once_and_is_idempotent(fake):
    connector, backend, _ = fake
    staged = connector.dispatch(
        agent_id="hermes-operator",
        tool="qbo_create_invoice_draft",
        arguments={"customer_id": "1", "line_amount": 10},
    )
    action_id = staged["data"]["action"]["id"]
    connector.operator_decide(action_id, decision="approved", user="operator")
    first = connector.operator_execute(action_id, user="operator")
    assert first["status"] == "executed"
    assert first["qbo_object_id"] == "99"
    assert backend.post_count == 1
    second = connector.operator_execute(action_id, user="operator")
    assert second["status"] == "executed"
    assert backend.post_count == 1


def test_write_failure_is_not_retried(fake):
    connector, backend, _ = fake
    backend.fail_posts = 5
    staged = connector.dispatch(
        agent_id="hermes-operator",
        tool="qbo_create_invoice_draft",
        arguments={"customer_id": "1", "line_amount": 10},
    )
    action_id = staged["data"]["action"]["id"]
    connector.operator_decide(action_id, decision="approved", user="operator")
    result = connector.operator_execute(action_id, user="operator")
    assert result["status"] == "failed"
    assert backend.post_count == 1
