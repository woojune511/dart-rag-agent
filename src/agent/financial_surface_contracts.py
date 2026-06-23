"""Operand surface-contract helpers."""

from __future__ import annotations

import re
from typing import Any, Dict, List

from src.agent.financial_runtime_normalization import _normalise_spaces
from src.config.retrieval_policy import HELPER_RUNTIME_POLICY


def _operand_needles(operand: Dict[str, Any]) -> List[str]:
    label = str(operand.get("label") or "").strip()
    aliases = [str(item).strip() for item in (operand.get("aliases") or []) if str(item).strip()]
    return [needle for needle in [label, *aliases] if needle]


def _operand_surface_contract(operand: Dict[str, Any]) -> Dict[str, List[str]]:
    explicit_contract = dict(operand.get("surface_contract") or {})
    if explicit_contract:
        return {
            "positive": [str(item).strip() for item in (explicit_contract.get("positive") or []) if str(item).strip()],
            "negative": [str(item).strip() for item in (explicit_contract.get("negative") or []) if str(item).strip()],
        }

    concept_key = _normalise_spaces(str(operand.get("concept") or ""))
    legacy_contracts = {
        str(key): dict(value or {})
        for key, value in dict(HELPER_RUNTIME_POLICY.get("legacy_concept_surface_contracts") or {}).items()
    }
    if concept_key and concept_key in legacy_contracts:
        return dict(legacy_contracts[concept_key])

    needles = " ".join(_operand_needles(operand))
    for contract in legacy_contracts.values():
        positive_terms = [str(item).strip() for item in (contract.get("positive") or []) if str(item).strip()]
        if any(_normalise_spaces(term) in _normalise_spaces(needles) for term in positive_terms):
            return dict(contract)
    return {}


def _text_has_contract_term(text: str, terms: List[str]) -> bool:
    haystack = _normalise_spaces(text or "")
    if not haystack:
        return False
    haystack_compact = re.sub(r"\s+", "", haystack)
    for raw_term in terms:
        normalized_term = _normalise_spaces(raw_term)
        if not normalized_term:
            continue
        term_compact = re.sub(r"\s+", "", normalized_term)
        if normalized_term in haystack or (term_compact and term_compact in haystack_compact):
            return True
    return False


def _text_has_positive_surface(text: str, operand: Dict[str, Any]) -> bool:
    contract = _operand_surface_contract(operand)
    return _text_has_contract_term(text, list(contract.get("positive") or []))


def _text_has_negative_surface(text: str, operand: Dict[str, Any]) -> bool:
    contract = _operand_surface_contract(operand)
    return _text_has_contract_term(text, list(contract.get("negative") or []))
