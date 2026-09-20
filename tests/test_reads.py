def test_company_info_and_overdue(fake):
    connector, _, _ = fake
    company = connector.dispatch(agent_id="hermes-operator", tool="qbo_get_company_info", arguments={})
    assert company["ok"] is True
    assert company["data"]["CompanyName"] == "Sandbox Co"
    overdue = connector.dispatch(agent_id="hermes-operator", tool="qbo_get_overdue_invoices", arguments={})
    assert overdue["ok"] is True
    assert overdue["data"]["entities"][0]["days_overdue_kind"] == "calculated"


def test_pnl_report_metadata(fake):
    connector, _, _ = fake
    result = connector.dispatch(agent_id="hermes-operator", tool="qbo_profit_and_loss", arguments={"period": "this_month"})
    assert result["ok"] is True
    assert result["date_range"]["start"] == "2026-09-01"
    assert result["report_basis"] == "Accrual"


def test_rate_limit_retries_reads(fake):
    connector, backend, _ = fake
    backend.rate_limit_reads = 1
    result = connector.dispatch(agent_id="hermes-operator", tool="qbo_search_customers", arguments={})
    assert result["ok"] is True
    assert len([c for c in backend.calls if "/query" in str(c.url)]) >= 2


def test_expense_uses_purchase_entity(fake):
    connector, _, _ = fake
    result = connector.dispatch(agent_id="hermes-operator", tool="qbo_summarize_expenses", arguments={"period": "this_month"})
    assert result["value_kind"] == "calculated"
    names = {row["account"] for row in result["data"]["categories"]}
    assert "Software" in names
