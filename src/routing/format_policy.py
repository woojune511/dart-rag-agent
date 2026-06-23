"""Lightweight routing format policy helpers."""

from typing import Dict


ROUTER_INTENTS: tuple[str, ...] = ("numeric_fact", "business_overview", "risk", "comparison", "trend", "qa")
FORMAT_PREFERENCE_BY_INTENT: Dict[str, str] = {
    "numeric_fact": "table",
    "business_overview": "mixed",
    "risk": "paragraph",
    "comparison": "table",
    "trend": "table",
    "qa": "paragraph",
}


def default_format_preference(intent: str) -> str:
    return FORMAT_PREFERENCE_BY_INTENT.get(intent, "mixed")
