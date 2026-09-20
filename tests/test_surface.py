from hermes_qbo.catalog import TOOLS


def test_search_estimate_and_preferences(fake):
    connector, _, _ = fake
    estimates = connector.dispatch(agent_id="hermes-operator", tool="qbo_search_estimates", arguments={})
    assert estimates["ok"] is True
    assert estimates["data"]["entities"] == []
    prefs = connector.dispatch(agent_id="hermes-operator", tool="qbo_get_preferences", arguments={})
    assert prefs["ok"] is True
    assert "Preferences" in prefs["data"] or "AccountingInfoPrefs" in str(prefs["data"])


def test_get_item_and_trial_balance(fake):
    connector, _, _ = fake
    item = connector.dispatch(agent_id="hermes-operator", tool="qbo_get_item", arguments={"item_id": "7"})
    assert item["ok"] is True
    report = connector.dispatch(agent_id="hermes-operator", tool="qbo_trial_balance", arguments={"period": "this_month"})
    assert report["ok"] is True
    assert report["data"]["report"] == "TrialBalance"


def test_estimate_draft_stays_local(fake):
    connector, backend, _ = fake
    result = connector.dispatch(
        agent_id="hermes-operator",
        tool="qbo_create_estimate_draft",
        arguments={"customer_id": "1", "line_amount": 50},
    )
    assert result["posted_to_quickbooks"] is False
    assert backend.post_count == 0
    assert TOOLS["qbo_create_estimate_draft"]["risk"] == "draft"
