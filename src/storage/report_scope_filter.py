"""Exact caller metadata constraints, independent of question interpretation."""

from typing import Any


_FIELDS = {"company": "company", "corp_name": "company", "year": "year",
           "report_type": "report_type", "rcept_no": "rcept_no",
           "consolidation": "consolidation_scope"}
_LIST_FIELDS = {"source_companies": "company", "source_receipts": "rcept_no"}


def _conjunction(clauses: list[dict]) -> dict | None:
    return clauses[0] if len(clauses) == 1 else {"$and": clauses} if clauses else None


def report_scope_filter(scope: dict[str, Any]) -> dict | None:
    """Intersect all supplied fields; source_reports is a union of exact tuples.

    Empty optional lists mean unspecified, as in the HTTP request schema.
    Invalid/unknown constraints fail rather than silently broadening a search.
    """
    if set(scope) - (_FIELDS.keys() | _LIST_FIELDS.keys() | {"source_reports"}):
        raise ValueError("Unsupported report scope field")
    clauses = []
    for source, target in _FIELDS.items():
        value = scope.get(source)
        if value is None or value == "":
            continue
        if source == "year":
            if type(value) is not int:
                raise ValueError("Report year must be an integer")
        elif not isinstance(value, str) or not value.strip():
            raise ValueError("Report scope values must be nonempty strings")
        clauses.append({target: value.strip() if isinstance(value, str) else value})
    for source, target in _LIST_FIELDS.items():
        values = scope.get(source, [])
        if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values):
            raise ValueError("Report scope lists must contain nonempty strings")
        if values:
            clauses.append({target: {"$in": list(dict.fromkeys(v.strip() for v in values))}})
    reports = scope.get("source_reports", [])
    if not isinstance(reports, list):
        raise ValueError("Source reports must be a list")
    alternatives = []
    for report in reports:
        if not isinstance(report, dict) or set(report) - _FIELDS.keys():
            raise ValueError("Invalid source report constraint")
        condition = report_scope_filter(report)
        if not condition:
            raise ValueError("Source report constraint cannot be empty")
        alternatives.append(condition)
    if alternatives:
        clauses.append(alternatives[0] if len(alternatives) == 1 else {"$or": alternatives})
    return _conjunction(clauses)
