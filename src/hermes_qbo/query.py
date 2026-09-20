from __future__ import annotations

import re

from .api_surface import query_fields

SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
SAFE_TEXT = re.compile(r"^[\w .,&@#'\-\+]{1,80}$")
ENTITY_FIELDS = query_fields()


class QueryError(ValueError):
    pass


def _esc(value: str) -> str:
    if not isinstance(value, str):
        value = str(value)
    if len(value) > 80:
        raise QueryError("value_too_long")
    if "'" in value or "\\" in value or "\n" in value:
        raise QueryError("value_not_allowed")
    return f"'{value}'"


def compile_query(
    entity: str,
    *,
    filters: list[tuple[str, str, str]] | None = None,
    order_by: str | None = None,
    maxresults: int = 50,
) -> str:
    if entity not in ENTITY_FIELDS:
        raise QueryError("unknown_entity")
    maxresults = max(1, min(int(maxresults), 100))
    clauses: list[str] = []
    allowed = ENTITY_FIELDS[entity]
    for field, op, value in filters or []:
        if field not in allowed:
            raise QueryError(f"field_not_allowed:{field}")
        if op not in {"=", ">", "<", ">=", "<=", "LIKE", "!="}:
            raise QueryError("op_not_allowed")
        if op == "LIKE":
            core = value.replace("%", "")
            if len(core) > 80 or any(ch in value for ch in "'\\\n"):
                raise QueryError("like_not_allowed")
            clauses.append(f"{field} LIKE {_esc(value)}")
        else:
            clauses.append(f"{field} {op} {_esc(value)}")
    sql = f"SELECT * FROM {entity}"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    if order_by:
        field = order_by.lstrip("-")
        if field not in allowed:
            raise QueryError("order_not_allowed")
        direction = "DESC" if order_by.startswith("-") else "ASC"
        sql += f" ORDERBY {field} {direction}"
    sql += f" MAXRESULTS {maxresults}"
    return sql
