from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def _normalise_spaces(text: str) -> str:
    return " ".join(str(text or "").split()).strip().lower()


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

    def match_metric_families(self, query: str, topic: str = "", intent: str = "") -> List[Dict[str, Any]]:
        if intent and intent not in {"comparison", "trend"}:
            return []
        combined = _normalise_spaces(f"{query} {topic}")
        matches: List[tuple[int, str, Dict[str, Any]]] = []
        for key, metric in self.metric_families.items():
            keywords = [str(keyword).strip() for keyword in metric.get("intent_keywords", []) if str(keyword).strip()]
            score = sum(1 for keyword in keywords if _normalise_spaces(keyword) in combined)
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

    def preferred_sections(self, query: str, topic: str = "", intent: str = "") -> List[str]:
        sections: List[str] = []
        for metric in self.match_metric_families(query, topic, intent):
            sections.extend(str(section).strip() for section in metric.get("preferred_sections", []) if str(section).strip())
        return list(dict.fromkeys(sections))

    def supplement_sections(self, query: str, topic: str = "", intent: str = "") -> List[str]:
        sections: List[str] = []
        for metric in self.match_metric_families(query, topic, intent):
            sections.extend(str(section).strip() for section in metric.get("supplement_sections", []) if str(section).strip())
        return list(dict.fromkeys(sections))

    def query_hints(self, query: str, topic: str = "", intent: str = "") -> List[str]:
        hints: List[str] = []
        for metric in self.match_metric_families(query, topic, intent):
            hints.extend(str(hint).strip() for hint in metric.get("query_hints", []) if str(hint).strip())
            components = dict(metric.get("components") or {})
            for component in components.values():
                name = str(component.get("name") or "").strip()
                if name:
                    hints.append(name)
        return list(dict.fromkeys(hints))

    def row_patterns(self, query: str, topic: str = "", intent: str = "") -> List[str]:
        patterns: List[str] = []
        for metric in self.match_metric_families(query, topic, intent):
            patterns.extend(str(pattern).strip() for pattern in metric.get("row_patterns", []) if str(pattern).strip())
        return list(dict.fromkeys(patterns))

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
                        "keywords": [str(keyword).strip() for keyword in component.get("keywords", []) if str(keyword).strip()],
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
