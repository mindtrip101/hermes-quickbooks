from hermes_qbo.oauth import OAuthError


def test_authorize_url_includes_state_and_accounting_scope(fake):
    connector, _, _ = fake
    payload = connector.authorize_url("company_a")
    assert "state=" in payload["authorize_url"]
    assert "com.intuit.quickbooks.accounting" in payload["authorize_url"]
    assert payload["redirect_uri"] == "http://localhost:14112/oauth/callback"
    assert "127.0.0.1" not in payload["redirect_uri"]


def test_invalid_state_rejected(fake):
    connector, _, _ = fake
    try:
        connector.oauth.exchange_code(code="abc", state="nope", realm_id="realm-1")
        assert False
    except OAuthError as exc:
        assert exc.code == "invalid_state"


def test_refresh_persists_rotated_refresh_token(fake):
    connector, _, settings = fake
    tokens = connector.tokens.load("company_a")
    assert tokens.refresh_token == "refresh-aaa"
    tokens.access_expires_at = 1
    refreshed = connector.oauth.refresh("company_a", tokens)
    assert refreshed.refresh_token == "refresh-bbb"
    stored = connector.tokens.load("company_a")
    assert stored.refresh_token == "refresh-bbb"
    assert stored.access_token == "access-bbb"


def test_reauthorization_message_does_not_ask_for_password(fake, tmp_path):
    connector, _, _ = fake
    connector.tokens._path("company_a").unlink()
    result = connector.dispatch(agent_id="hermes-operator", tool="qbo_get_company_info", arguments={})
    assert result["ok"] is False
    assert "reauthorization_required" in result["errors"]
    message = result["data"]["message"].lower()
    assert "password" not in message or "do not send" in message
