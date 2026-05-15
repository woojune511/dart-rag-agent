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


def _best_alias_match_span(text: str, aliases: Iterable[str]) -> Optional[tuple[int, int]]:
    haystack = _normalise_spaces(text)
    best: Optional[tuple[int, int]] = None
    for raw_alias in aliases:
        alias = _normalise_spaces(raw_alias)
        if not alias:
            continue
        start = haystack.find(alias)
        if start < 0:
            continue
        end = start + len(alias)
        if best is None or (end - start) > (best[1] - best[0]):
            best = (start, end)
    return best


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

    @property
    def concepts(self) -> Dict[str, Dict[str, Any]]:
        return dict(self.payload.get("concepts") or {})

    @property
    def concept_groups(self) -> Dict[str, Dict[str, Any]]:
        return dict(self.payload.get("concept_groups") or {})

    @property
    def binding_policy_defaults(self) -> Dict[str, Any]:
        return dict(self.payload.get("binding_policy_defaults") or {})

    @property
    def planner_guidance(self) -> Dict[str, Any]:
        return dict(self.payload.get("planner_guidance") or {})

    def concept(self, key: str) -> Optional[Dict[str, Any]]:
        concept = self.concepts.get(key)
        if not concept:
            return None
        return {"key": key, **concept}

    def binding_policy_for_concept(self, key: str) -> Dict[str, Any]:
        concept = self.concepts.get(key) or {}
        return self._merge_binding_policy(self.binding_policy_defaults, concept.get("binding_policy"))

    def _merge_binding_policy(self, *policies: Any) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}
        for raw_policy in policies:
            if not isinstance(raw_policy, dict):
                continue
            for key, value in raw_policy.items():
                if isinstance(value, list):
                    merged[key] = _dedupe_preserve_order(value)
                elif value not in (None, ""):
                    merged[key] = value
        return merged

    def _component_payload(self, component: Dict[str, Any]) -> Dict[str, Any]:
        raw = dict(component or {})
        concept_key = str(raw.get("concept") or raw.get("concept_ref") or "").strip()
        concept = dict(self.concepts.get(concept_key) or {})
        name = (
            str(raw.get("name") or "").strip()
            or str(concept.get("display_name") or concept.get("name") or "").strip()
        )
        aliases = _dedupe_preserve_order([*(concept.get("aliases", []) or []), *(raw.get("aliases", []) or [])])
        keywords = _dedupe_preserve_order([*(concept.get("keywords", []) or []), *(raw.get("keywords", []) or [])])
        preferred_sections = _dedupe_preserve_order(
            [*(concept.get("preferred_sections", []) or []), *(raw.get("preferred_sections", []) or [])]
        )
        preferred_statement_types = _dedupe_preserve_order(
            [*(concept.get("preferred_statement_types", []) or []), *(raw.get("preferred_statement_types", []) or [])]
        )
        binding_policy = self._merge_binding_policy(
            self.binding_policy_defaults,
            concept.get("binding_policy"),
            raw.get("binding_policy"),
            raw.get("binding_policy_override"),
        )
        merged = {**concept, **raw}
        merged.update(
            {
                "concept": concept_key,
                "name": name,
                "display_name": str(concept.get("display_name") or name).strip(),
                "aliases": aliases,
                "keywords": keywords,
                "preferred_sections": preferred_sections,
                "preferred_statement_types": preferred_statement_types,
                "binding_policy": binding_policy,
                "unit_family": str(concept.get("unit_family") or raw.get("unit_family") or "").strip(),
            }
        )
        return merged

    def _metric_aliases(self, metric: Dict[str, Any]) -> List[str]:
        values = [metric.get("display_name", "")]
        values.extend(metric.get("aliases", []) or [])
        values.extend(metric.get("intent_keywords", []) or [])
        return _dedupe_preserve_order(values)

    def _component_aliases(self, component: Dict[str, Any]) -> List[str]:
        payload = self._component_payload(component)
        values = [payload.get("name", ""), payload.get("display_name", "")]
        values.extend(payload.get("aliases", []) or [])
        values.extend(payload.get("keywords", []) or [])
        return _dedupe_preserve_order(values)

    def _concept_aliases(self, concept: Dict[str, Any]) -> List[str]:
        values = [concept.get("display_name", ""), concept.get("name", "")]
        values.extend(concept.get("aliases", []) or [])
        values.extend(concept.get("keywords", []) or [])
        return _dedupe_preserve_order(values)

    def _group_aliases(self, group: Dict[str, Any]) -> List[str]:
        values = [group.get("display_name", ""), group.get("name", "")]
        values.extend(group.get("aliases", []) or [])
        values.extend(group.get("keywords", []) or [])
        return _dedupe_preserve_order(values)

    def _concept_spec_payload(self, key: str, concept: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "concept": str(key).strip(),
            "name": str(concept.get("display_name") or concept.get("name") or "").strip(),
            "aliases": self._concept_aliases(concept),
            "keywords": [str(keyword).strip() for keyword in concept.get("keywords", []) if str(keyword).strip()],
            "preferred_sections": [
                str(section).strip()
                for section in concept.get("preferred_sections", [])
                if str(section).strip()
            ],
            "preferred_statement_types": [
                str(item).strip()
                for item in concept.get("preferred_statement_types", [])
                if str(item).strip()
            ],
            "binding_policy": self._merge_binding_policy(
                self.binding_policy_defaults,
                concept.get("binding_policy"),
            ),
            "unit_family": str(concept.get("unit_family") or "").strip(),
        }

    def _group_spec_payload(self, key: str, group: Dict[str, Any]) -> Dict[str, Any]:
        member_keys = [
            str(member).strip()
            for member in group.get("member_concepts", [])
            if str(member).strip() and str(member).strip() in self.concepts
        ]
        member_specs = [
            self._concept_spec_payload(member_key, self.concepts[member_key])
            for member_key in member_keys
        ]
        preferred_sections = _dedupe_preserve_order(
            [
                *(group.get("preferred_sections", []) or []),
                *[
                    section
                    for member_spec in member_specs
                    for section in member_spec.get("preferred_sections", [])
                ],
            ]
        )
        preferred_statement_types = _dedupe_preserve_order(
            [
                *(group.get("preferred_statement_types", []) or []),
                *[
                    statement_type
                    for member_spec in member_specs
                    for statement_type in member_spec.get("preferred_statement_types", [])
                ],
            ]
        )
        return {
            "concept": str(key).strip(),
            "name": str(group.get("display_name") or group.get("name") or "").strip(),
            "aliases": self._group_aliases(group),
            "keywords": [str(keyword).strip() for keyword in group.get("keywords", []) if str(keyword).strip()],
            "preferred_sections": [str(section).strip() for section in preferred_sections if str(section).strip()],
            "preferred_statement_types": [
                str(item).strip()
                for item in preferred_statement_types
                if str(item).strip()
            ],
            "binding_policy": self._merge_binding_policy(
                self.binding_policy_defaults,
                group.get("binding_policy"),
            ),
            "unit_family": str(group.get("unit_family") or "").strip(),
            "is_group": True,
            "member_concepts": member_keys,
            "member_specs": member_specs,
        }

    def has_concept_key(self, key: str) -> bool:
        normalized = str(key or "").strip()
        return normalized in self.concepts or normalized in self.concept_groups

    def match_concepts(self, query: str, topic: str = "", intent: str = "") -> List[Dict[str, Any]]:
        combined = _normalise_spaces(f"{query} {topic}")
        matches: List[tuple[int, int, str, Dict[str, Any], tuple[int, int], bool]] = []
        for key, concept in self.concepts.items():
            score = 0
            aliases = self._concept_aliases(concept)
            for alias in aliases:
                if _normalise_spaces(alias) in combined:
                    score += 2
            if score > 0:
                best_span = _best_alias_match_span(combined, aliases)
                if best_span is None:
                    continue
                match_length = best_span[1] - best_span[0]
                matches.append((score, match_length, key, concept, best_span, False))
        for key, group in self.concept_groups.items():
            score = 0
            aliases = self._group_aliases(group)
            for alias in aliases:
                if _normalise_spaces(alias) in combined:
                    score += 2
            if score > 0:
                best_span = _best_alias_match_span(combined, aliases)
                if best_span is None:
                    continue
                match_length = best_span[1] - best_span[0]
                matches.append((score, match_length, key, group, best_span, True))
        matches.sort(key=lambda item: (item[0], item[1]), reverse=True)
        filtered: List[tuple[int, int, str, Dict[str, Any], tuple[int, int], bool]] = []
        for candidate in matches:
            _score, match_length, _key, _concept, span, _is_group = candidate
            shadowed = any(
                kept_span[0] <= span[0]
                and kept_span[1] >= span[1]
                and (kept_span[1] - kept_span[0]) > match_length
                for _kept_score, _kept_length, _kept_key, _kept_concept, kept_span, _kept_is_group in filtered
            )
            if shadowed:
                continue
            filtered.append(candidate)
        rows: List[Dict[str, Any]] = []
        for _score, _length, key, concept_like, _span, is_group in filtered:
            row = {"key": key, **concept_like}
            if is_group:
                row["is_group"] = True
            rows.append(row)
        return rows

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
            payload = self._component_payload(component)
            rows.append(
                {
                    "role": str(role).strip(),
                    "label": str(payload.get("name") or "").strip(),
                    "concept": str(payload.get("concept") or "").strip(),
                    "aliases": _dedupe_preserve_order(payload.get("aliases", []) or []),
                    "keywords": _dedupe_preserve_order(payload.get("keywords", []) or []),
                    "required": bool(payload.get("required", True)),
                    "preferred_sections": _dedupe_preserve_order(payload.get("preferred_sections", []) or []),
                    "preferred_statement_types": _dedupe_preserve_order(payload.get("preferred_statement_types", []) or []),
                    "binding_policy": dict(payload.get("binding_policy") or {}),
                    "unit_family": str(payload.get("unit_family") or "").strip(),
                }
            )
        return rows

    def preferred_sections(self, query: str, topic: str = "", intent: str = "") -> List[str]:
        sections: List[str] = []
        metric_matches = self.match_metric_families(query, topic, intent)
        if metric_matches:
            for metric in metric_matches:
                sections.extend(str(section).strip() for section in metric.get("preferred_sections", []) if str(section).strip())
        else:
            for concept in self.match_concepts(query, topic, intent):
                sections.extend(
                    str(section).strip()
                    for section in concept.get("preferred_sections", [])
                    if str(section).strip()
                )
        return _dedupe_preserve_order(sections)

    def supplement_sections(self, query: str, topic: str = "", intent: str = "") -> List[str]:
        sections: List[str] = []
        for metric in self.match_metric_families(query, topic, intent):
            sections.extend(str(section).strip() for section in metric.get("supplement_sections", []) if str(section).strip())
        return _dedupe_preserve_order(sections)

    def query_hints(self, query: str, topic: str = "", intent: str = "") -> List[str]:
        hints: List[str] = []
        metric_matches = self.match_metric_families(query, topic, intent)
        if metric_matches:
            for metric in metric_matches:
                hints.extend(str(hint).strip() for hint in metric.get("query_hints", []) if str(hint).strip())
                components = dict(metric.get("components") or {})
                for component in components.values():
                    hints.extend(self._component_aliases(component))
        else:
            for concept in self.match_concepts(query, topic, intent):
                hints.extend(self._concept_aliases(concept))
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
                payload = self._component_payload(component)
                specs.append(
                    {
                        "metric_key": metric.get("key"),
                        "metric_display_name": metric.get("display_name"),
                        "role": role,
                        "name": str(payload.get("name") or "").strip(),
                        "concept": str(payload.get("concept") or "").strip(),
                        "aliases": _dedupe_preserve_order(payload.get("aliases", []) or []),
                        "keywords": [str(keyword).strip() for keyword in payload.get("keywords", []) if str(keyword).strip()],
                        "required": bool(payload.get("required", True)),
                        "preferred_sections": [str(section).strip() for section in payload.get("preferred_sections", []) if str(section).strip()],
                        "preferred_statement_types": [
                            str(item).strip()
                            for item in payload.get("preferred_statement_types", [])
                            if str(item).strip()
                        ],
                        "binding_policy": dict(payload.get("binding_policy") or {}),
                    }
                )
        return specs

    def concept_specs(self, query: str, topic: str = "", intent: str = "") -> List[Dict[str, Any]]:
        specs: List[Dict[str, Any]] = []
        for concept in self.match_concepts(query, topic, intent):
            concept_key = str(concept.get("key") or "").strip()
            if concept.get("is_group"):
                specs.append(self._group_spec_payload(concept_key, concept))
            else:
                specs.append(self._concept_spec_payload(concept_key, concept))
        return specs

    def all_concept_specs(self) -> List[Dict[str, Any]]:
        specs: List[Dict[str, Any]] = []
        for key, concept in self.concepts.items():
            specs.append(self._concept_spec_payload(key, concept))
        for key, group in self.concept_groups.items():
            specs.append(self._group_spec_payload(key, group))
        return specs


_ONTOLOGY_SINGLETON: Optional[FinancialOntologyManager] = None


def get_financial_ontology() -> FinancialOntologyManager:
    global _ONTOLOGY_SINGLETON
    if _ONTOLOGY_SINGLETON is None:
        _ONTOLOGY_SINGLETON = FinancialOntologyManager()
    return _ONTOLOGY_SINGLETON
