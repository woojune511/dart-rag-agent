from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def _normalise_spaces(text: str) -> str:
    return " ".join(str(text or "").split()).strip().lower()


def _dedupe_preserve_order(values: Iterable[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for raw in values:
        value = str(raw or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


class FinancialOntologyManager:
    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or Path(__file__).resolve().with_name("financial_ontology.json")
        self.payload = self._load()

    def _load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"metric_families": {}}
        return json.loads(self.path.read_text(encoding="utf-8"))

    @property
    def metric_families(self) -> Dict[str, Dict[str, Any]]:
        return dict(self.payload.get("metric_families") or {})

    def _metric_aliases(self, metric: Dict[str, Any]) -> List[str]:
        values = [metric.get("display_name", "")]
        values.extend(metric.get("aliases", []) or [])
        values.extend(metric.get("intent_keywords", []) or [])
        return _dedupe_preserve_order(values)

    def _component_aliases(self, component: Dict[str, Any]) -> List[str]:
        values = [component.get("name", "")]
        values.extend(component.get("aliases", []) or [])
        values.extend(component.get("keywords", []) or [])
        return _dedupe_preserve_order(values)

    def match_metric_families(self, query: str, topic: str = "", intent: str = "") -> List[Dict[str, Any]]:
        combined = _normalise_spaces(f"{query} {topic}")
        matches: List[tuple[int, str, Dict[str, Any]]] = []
        for key, metric in self.metric_families.items():
            score = 0
            for alias in self._metric_aliases(metric):
                if _normalise_spaces(alias) in combined:
                    score += 3
            components = dict(metric.get("components") or {})
            for component in components.values():
                for alias in self._component_aliases(component):
                    if _normalise_spaces(alias) in combined:
                        score += 1
            if score > 0:
                matches.append((score, key, metric))
        matches.sort(key=lambda item: item[0], reverse=True)
        return [{"key": key, **metric} for _score, key, metric in matches]

    def best_metric_family(self, query: str, topic: str = "", intent: str = "") -> Optional[Dict[str, Any]]:
        matches = self.match_metric_families(query, topic, intent)
        return matches[0] if matches else None

    def metric_family(self, key: str) -> Optional[Dict[str, Any]]:
        metric = self.metric_families.get(key)
        if not metric:
            return None
        return {"key": key, **metric}

    def aliases_for_metric(self, key: str) -> List[str]:
        metric = self.metric_families.get(key) or {}
        return self._metric_aliases(metric)

    def statement_type_hints_for_metric(self, key: str) -> List[str]:
        metric = self.metric_families.get(key) or {}
        return _dedupe_preserve_order(metric.get("statement_type_hints", []) or [])

    def retrieval_keywords_for_metric(self, key: str) -> List[str]:
        metric = self.metric_families.get(key) or {}
        values = list(metric.get("retrieval_keywords", []) or [])
        values.extend(metric.get("query_hints", []) or [])
        components = dict(metric.get("components") or {})
        for component in components.values():
            values.extend(self._component_aliases(component))
        return _dedupe_preserve_order(values)

    def default_constraints_for_metric(self, key: str) -> Dict[str, Any]:
        metric = self.metric_families.get(key) or {}
        constraints = dict(metric.get("default_constraints") or {})
        return {
            "consolidation_scope": str(constraints.get("consolidation_scope") or "unknown"),
            "period_focus": str(constraints.get("period_focus") or "unknown"),
            "entity_scope": str(constraints.get("entity_scope") or "unknown"),
            "segment_scope": str(constraints.get("segment_scope") or "none"),
        }

    def formula_family_for_metric(self, key: str) -> str:
        metric = self.metric_families.get(key) or {}
        return str(metric.get("formula_family") or "")

    def build_operand_spec(self, key: str) -> List[Dict[str, Any]]:
        metric = self.metric_families.get(key) or {}
        components = dict(metric.get("components") or {})
        rows: List[Dict[str, Any]] = []
        for role, component in components.items():
            rows.append(
                {
                    "role": str(role).strip(),
                    "label": str(component.get("name") or "").strip(),
                    "aliases": _dedupe_preserve_order(component.get("aliases", []) or []),
                    "keywords": _dedupe_preserve_order(component.get("keywords", []) or []),
                    "required": bool(component.get("required", True)),
                    "preferred_sections": _dedupe_preserve_order(component.get("preferred_sections", []) or []),
                }
            )
        return rows

    def preferred_sections(self, query: str, topic: str = "", intent: str = "") -> List[str]:
        sections: List[str] = []
        for metric in self.match_metric_families(query, topic, intent):
            sections.extend(str(section).strip() for section in metric.get("preferred_sections", []) if str(section).strip())
        return _dedupe_preserve_order(sections)

    def supplement_sections(self, query: str, topic: str = "", intent: str = "") -> List[str]:
        sections: List[str] = []
        for metric in self.match_metric_families(query, topic, intent):
            sections.extend(str(section).strip() for section in metric.get("supplement_sections", []) if str(section).strip())
        return _dedupe_preserve_order(sections)

    def query_hints(self, query: str, topic: str = "", intent: str = "") -> List[str]:
        hints: List[str] = []
        for metric in self.match_metric_families(query, topic, intent):
            hints.extend(str(hint).strip() for hint in metric.get("query_hints", []) if str(hint).strip())
            components = dict(metric.get("components") or {})
            for component in components.values():
                hints.extend(self._component_aliases(component))
        return _dedupe_preserve_order(hints)

    def row_patterns(self, query: str, topic: str = "", intent: str = "") -> List[str]:
        patterns: List[str] = []
        for metric in self.match_metric_families(query, topic, intent):
            patterns.extend(str(pattern).strip() for pattern in metric.get("row_patterns", []) if str(pattern).strip())
        return _dedupe_preserve_order(patterns)

    def component_specs(self, query: str, topic: str = "", intent: str = "") -> List[Dict[str, Any]]:
        specs: List[Dict[str, Any]] = []
        for metric in self.match_metric_families(query, topic, intent):
            components = dict(metric.get("components") or {})
            for role, component in components.items():
                specs.append(
                    {
                        "metric_key": metric.get("key"),
                        "metric_display_name": metric.get("display_name"),
                        "role": role,
                        "name": str(component.get("name") or "").strip(),
                        "aliases": _dedupe_preserve_order(component.get("aliases", []) or []),
                        "keywords": [str(keyword).strip() for keyword in component.get("keywords", []) if str(keyword).strip()],
                        "required": bool(component.get("required", True)),
                        "preferred_sections": [str(section).strip() for section in component.get("preferred_sections", []) if str(section).strip()],
                    }
                )
        return specs


_ONTOLOGY_SINGLETON: Optional[FinancialOntologyManager] = None


def get_financial_ontology() -> FinancialOntologyManager:
    global _ONTOLOGY_SINGLETON
    if _ONTOLOGY_SINGLETON is None:
        _ONTOLOGY_SINGLETON = FinancialOntologyManager()
    return _ONTOLOGY_SINGLETON
