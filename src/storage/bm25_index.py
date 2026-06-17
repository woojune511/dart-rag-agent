import re
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.documents import Document


def tokenize_ko(text: str) -> List[str]:
    """Tokenize Korean with character bigrams plus ASCII word tokens."""
    tokens: List[str] = []
    for segment in re.findall(r"[가-힣]+|[a-zA-Z0-9]+", text):
        if re.fullmatch(r"[가-힣]+", segment):
            if len(segment) == 1:
                tokens.append(segment)
            else:
                tokens.extend(segment[i : i + 2] for i in range(len(segment) - 1))
        else:
            tokens.append(segment.lower())
    return tokens


def metadata_matches_filter(metadata: Dict[str, Any], where_filter: Optional[dict]) -> bool:
    if not where_filter:
        return True

    if "$and" in where_filter:
        return all(metadata_matches_filter(metadata, clause) for clause in where_filter["$and"])

    for key, expected in where_filter.items():
        actual = metadata.get(key)
        if isinstance(expected, dict):
            if "$in" in expected:
                expected_values = expected["$in"]
                if actual not in expected_values and str(actual) not in {str(value) for value in expected_values}:
                    return False
            else:
                return False
        else:
            if actual != expected and str(actual) != str(expected):
                return False
    return True


def build_bm25_index(docs: List[str], metadatas: List[dict]) -> Tuple[Any, List[str], List[dict]]:
    from rank_bm25 import BM25Okapi

    tokenized_corpus = [tokenize_ko(doc) for doc in docs]
    return BM25Okapi(tokenized_corpus), list(docs), list(metadatas or [{} for _ in docs])


def collect_bm25_results(
    bm25: Any,
    docs: List[str],
    metadatas: List[dict],
    query: str,
    *,
    k: int,
    where_filter: Optional[dict] = None,
) -> List[Tuple[Document, float]]:
    if not bm25:
        return []

    tokenized_query = tokenize_ko(query)
    bm25_scores = bm25.get_scores(tokenized_query)
    top_n = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[: k * 3]

    results: List[Tuple[Document, float]] = []
    for idx in top_n:
        if bm25_scores[idx] <= 0:
            continue
        metadata = metadatas[idx] or {}
        if not metadata_matches_filter(metadata, where_filter):
            continue
        doc = Document(page_content=docs[idx], metadata=metadata)
        results.append((doc, bm25_scores[idx]))
    return results
