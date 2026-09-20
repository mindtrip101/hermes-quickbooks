from hermes_qbo.api_surface import ENTITIES, REPORTS
from hermes_qbo.catalog import TOOL_NAMES, TOOLS


def test_tool_schemas_are_objects():
    assert "qbo_health" in TOOL_NAMES
    assert "qbo_create_invoice_draft" in TOOLS
    for name, spec in TOOLS.items():
        schema = spec["schema"]
        assert schema["type"] == "object"
        assert schema.get("additionalProperties") is False
        assert spec["risk"] in {"read", "draft", "write"}
        assert "description" in spec


def test_official_entities_are_registered():
    for spec in ENTITIES:
        assert spec["search_tool"] in TOOLS
        assert spec["get_tool"] in TOOLS
        assert TOOLS[spec["search_tool"]]["kind"] == "entity_search"
        assert TOOLS[spec["get_tool"]]["kind"] == "entity_get"


def test_official_reports_are_registered():
    for spec in REPORTS:
        assert spec["tool"] in TOOLS
    assert "qbo_get_preferences" in TOOLS
    assert "qbo_create_estimate_draft" in TOOLS
