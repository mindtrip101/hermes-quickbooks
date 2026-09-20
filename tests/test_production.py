from hermes_qbo.oauth import OAuthError
from hermes_qbo.service import ConnectorError
from hermes_qbo.tenants import Tenant


def test_production_execute_held_even_when_env_is_production(fake):
    connector, backend, _ = fake
    old = connector.tenants["company_a"]
    connector.tenants["company_a"] = Tenant(
        tenant_id=old.tenant_id,
        display_name="Live Company LLC",
        environment="production",
        credentials_ref=old.credentials_ref,
        allowed_agents=old.allowed_agents,
    )
    staged = connector.dispatch(
        agent_id="hermes-operator",
        tool="qbo_create_invoice_draft",
        arguments={"customer_id": "1", "line_amount": 10},
    )
    action_id = staged["data"]["action"]["id"]
    connector.operator_decide(action_id, decision="approved", user="operator")
    try:
        connector.operator_execute(action_id, user="operator")
        assert False
    except ConnectorError as exc:
        assert exc.code == "production_writes_held"
    assert backend.post_count == 0


def test_second_tenant_cannot_reuse_same_realm(fake):
    connector, _, _ = fake
    tokens = connector.tokens.load("company_a")
    try:
        connector.oauth.import_tokens(
            "company_b",
            realm_id=tokens.realm_id,
            access_token="aaa",
            refresh_token="bbb",
            environment="production",
        )
        assert False
    except OAuthError as exc:
        assert exc.code == "realm_in_use"


def test_import_tokens_stores_public_status_only(fake):
    connector, _, _ = fake
    result = connector.import_tokens(
        "company_a",
        {
            "realm_id": "realm-live-1",
            "access_token": "access-live",
            "refresh_token": "refresh-live",
            "environment": "production",
            "company_name": "Live Company LLC",
        },
    )
    assert result["ok"] is True
    assert result["company"] == "Live Company LLC"
    assert "access_token" not in result
    stored = connector.tokens.load("company_a")
    assert stored.environment == "production"
    assert stored.realm_id == "realm-live-1"


def test_health_lists_both_tenants(fake):
    health = fake[0].health()
    assert "company_a" in health["tenants"]
    assert "company_b" in health["tenants"]
    assert health["allow_production_writes"] is False
