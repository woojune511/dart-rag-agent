"""Apply explicitly selected lexical hints without changing the dense query."""
from dataclasses import dataclass
import re

from src.config.retrieval_policy import EXPERIMENTAL_LEXICAL_QUERY_POLICIES


@dataclass(frozen=True)
class LexicalQuery:
    query: str
    policy_id: str | None
    matched_rules: tuple[str, ...] = ()
    added_terms: tuple[str, ...] = ()


def resolve_lexical_query(query: str, policy_id: str | None = None) -> LexicalQuery:
    if policy_id is None:
        return LexicalQuery(query, None)
    if not isinstance(policy_id, str) or policy_id not in EXPERIMENTAL_LEXICAL_QUERY_POLICIES:
        raise ValueError("Unknown experimental lexical query policy")
    matched, added = [], []
    for rule in EXPERIMENTAL_LEXICAL_QUERY_POLICIES[policy_id]:
        if re.search(rule["query_pattern"], query) is None:
            continue
        matched.append(rule["id"])
        for term in rule["append_terms"]:
            if term not in query and term not in added:
                added.append(term)
    effective_query = query + " " + " ".join(added) if added else query
    return LexicalQuery(effective_query, policy_id, tuple(matched), tuple(added))
