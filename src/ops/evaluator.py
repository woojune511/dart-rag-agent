"""
RAG evaluation pipeline for DART analysis.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import mlflow
import numpy as np
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings

from storage.vector_store import DEFAULT_COLLECTION_NAME, DEFAULT_EMBEDDING_MODEL

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DATASET = _PROJECT_ROOT / "data" / "eval" / "eval_dataset.json"


@dataclass
class EvalExample:
    id: str
    question: str
    ground_truth: str
    company: str
    year: int
    section: str
    category: Optional[str] = None


@dataclass
class EvalResult:
    id: str
    question: str
    answer: str
    ground_truth: str
    faithfulness: float
    answer_relevancy: float
    context_recall: float
    retrieval_hit_at_k: float
    section_match_rate: float
    citation_coverage: float
    retrieved_count: int
    query_type: str
    latency_sec: float
    error: Optional[str] = None

    @property
    def aggregate_score(self) -> float:
        metrics = [
            self.faithfulness,
            self.answer_relevancy,
            self.context_recall,
            self.retrieval_hit_at_k,
            self.section_match_rate,
            self.citation_coverage,
        ]
        return sum(metrics) / len(metrics)


_FAITHFULNESS_PROMPT = """\
다음은 검색된 컨텍스트와 그에 대한 답변입니다.
답변이 컨텍스트에서만 근거한 내용인지 평가해주세요.

[컨텍스트]
{context}

[답변]
{answer}

평가 기준:
- 1.0: 답변의 모든 내용이 컨텍스트에 명확히 근거함
- 0.7: 대체로 근거하나 일부 해석/요약이 포함됨
- 0.5: 절반 정도만 근거하고 나머지는 추론이 큼
- 0.3: 컨텍스트와 약하게만 연결됨
- 0.0: 컨텍스트에 없는 내용이 대부분임

숫자(0.0~1.0)만 답하세요."""


def _tokenize_ko(text: str) -> set[str]:
    tokens = re.findall(r"[가-힣A-Za-z0-9]+", text or "")
    return {token.lower() for token in tokens if len(token) >= 2}


def _contains_section(metadata: Dict[str, Any], expected_section: str) -> bool:
    section = str(metadata.get("section", ""))
    section_path = str(metadata.get("section_path", ""))
    return expected_section == section or expected_section in section_path


def _compute_faithfulness(llm: ChatGoogleGenerativeAI, answer: str, contexts: List[str]) -> float:
    if not answer or not contexts:
        return 0.0

    context_text = "\n\n---\n\n".join(contexts[:5])
    prompt = _FAITHFULNESS_PROMPT.format(context=context_text[:4000], answer=answer[:1500])
    try:
        response = llm.invoke(prompt)
        text = response.content.strip()
        match = re.search(r"(0(?:\.\d+)?|1(?:\.0+)?)", text)
        return float(match.group(1)) if match else 0.5
    except Exception as exc:
        logger.warning("faithfulness calculation failed: %s", exc)
        return 0.5


def _compute_answer_relevancy(
    embeddings: HuggingFaceEmbeddings,
    question: str,
    answer: str,
) -> float:
    if not answer:
        return 0.0

    try:
        q_vec = np.array(embeddings.embed_query(question))
        a_vec = np.array(embeddings.embed_query(answer))
        cosine = np.dot(q_vec, a_vec) / (np.linalg.norm(q_vec) * np.linalg.norm(a_vec) + 1e-9)
        return float(np.clip(cosine, 0.0, 1.0))
    except Exception as exc:
        logger.warning("answer_relevancy calculation failed: %s", exc)
        return 0.5


def _compute_context_recall(ground_truth: str, contexts: List[str]) -> float:
    if not ground_truth or not contexts:
        return 0.0

    context_tokens = _tokenize_ko(" ".join(contexts))
    sentences = re.split(r"[.\n!?]", ground_truth)
    sentences = [sentence.strip() for sentence in sentences if len(sentence.strip()) >= 6]
    if not sentences:
        return 0.0

    covered = 0
    for sentence in sentences:
        sentence_tokens = _tokenize_ko(sentence)
        if not sentence_tokens:
            continue
        overlap = sentence_tokens & context_tokens
        if len(overlap) / len(sentence_tokens) >= 0.5:
            covered += 1

    return covered / len(sentences)


def _compute_retrieval_hit_at_k(example: EvalExample, retrieved_docs: List[Any]) -> float:
    expected_company = example.company.lower()
    for item in retrieved_docs:
        doc = item[0] if isinstance(item, (tuple, list)) else item
        metadata = getattr(doc, "metadata", {}) or {}
        company = str(metadata.get("company", "")).lower()
        year = int(metadata.get("year", 0) or 0)
        if company == expected_company and year == int(example.year) and _contains_section(metadata, example.section):
            return 1.0
    return 0.0


def _compute_section_match_rate(example: EvalExample, retrieved_docs: List[Any]) -> float:
    if not retrieved_docs:
        return 0.0
    matched = 0
    for item in retrieved_docs:
        doc = item[0] if isinstance(item, (tuple, list)) else item
        metadata = getattr(doc, "metadata", {}) or {}
        if _contains_section(metadata, example.section):
            matched += 1
    return matched / len(retrieved_docs)


def _compute_citation_coverage(example: EvalExample, citations: List[str]) -> float:
    if not citations:
        return 0.0

    citation_blob = " ".join(citations).lower()
    checks = [
        example.company.lower() in citation_blob,
        str(example.year) in citation_blob,
        example.section.lower() in citation_blob,
    ]
    return sum(1.0 for matched in checks if matched) / len(checks)


class RAGEvaluator:
    def __init__(
        self,
        agent,
        dataset_path: Optional[str] = None,
        experiment_name: str = "dart_rag_eval",
    ):
        self.agent = agent
        self.experiment_name = experiment_name
        self._dataset_path = Path(dataset_path) if dataset_path else _DEFAULT_DATASET
        self._llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.0)
        self._embeddings = HuggingFaceEmbeddings(model_name=DEFAULT_EMBEDDING_MODEL)

    def load_dataset(self) -> List[EvalExample]:
        with open(self._dataset_path, encoding="utf-8") as file:
            data = json.load(file)
        return [
            EvalExample(
                id=item["id"],
                question=item["question"],
                ground_truth=item["ground_truth"],
                company=item["company"],
                year=item["year"],
                section=item["section"],
                category=item.get("category"),
            )
            for item in data
        ]

    def build_single_company_eval_slice(
        self,
        examples: Optional[List[EvalExample]] = None,
        max_questions: int = 5,
    ) -> List[EvalExample]:
        if examples is None:
            examples = self.load_dataset()

        buckets = {
            "numeric_fact": None,
            "risk_analysis": None,
            "business_overview": None,
            "r_and_d_investment": None,
            "missing_information": None,
        }

        for example in examples:
            question = example.question.lower()
            section = example.section.lower()
            category = (example.category or "").lower()

            if buckets["numeric_fact"] is None and (
                category == "numeric_fact"
                or any(term in question for term in ("매출", "영업이익", "부채", "수치", "금액"))
            ):
                buckets["numeric_fact"] = example
            elif buckets["risk_analysis"] is None and (
                category == "risk_analysis" or "리스크" in section or "위험" in question
            ):
                buckets["risk_analysis"] = example
            elif buckets["business_overview"] is None and (
                category == "business_overview" or "사업개요" in section or "사업" in question
            ):
                buckets["business_overview"] = example
            elif buckets["r_and_d_investment"] is None and (
                category == "r_and_d_investment"
                or "연구개발" in section
                or any(term in question for term in ("r&d", "연구개발", "투자"))
            ):
                buckets["r_and_d_investment"] = example
            elif buckets["missing_information"] is None and (
                category == "missing_information"
                or any(term in question for term in ("없", "확인되지", "공시 문서에서"))
            ):
                buckets["missing_information"] = example

        selected = [example for example in buckets.values() if example is not None]
        if len(selected) < max_questions:
            seen_ids = {example.id for example in selected}
            for example in examples:
                if example.id in seen_ids:
                    continue
                selected.append(example)
                seen_ids.add(example.id)
                if len(selected) >= max_questions:
                    break

        return selected[:max_questions]

    def evaluate_one(self, example: EvalExample) -> EvalResult:
        started_at = time.time()
        error = None
        answer = ""
        contexts: List[str] = []
        query_type = "unknown"
        retrieved_docs: List[Any] = []
        citations: List[str] = []

        try:
            result = self.agent.run(example.question)
            answer = result.get("answer", "")
            query_type = result.get("query_type", "unknown")
            retrieved_docs = result.get("retrieved_docs", [])
            citations = result.get("citations", [])
            for item in retrieved_docs:
                doc = item[0] if isinstance(item, (tuple, list)) else item
                contexts.append(getattr(doc, "content", None) or getattr(doc, "page_content", ""))
        except Exception as exc:
            error = str(exc)
            logger.error("[%s] agent.run failed: %s", example.id, exc)

        latency = time.time() - started_at

        faithfulness = _compute_faithfulness(self._llm, answer, contexts)
        answer_relevancy = _compute_answer_relevancy(self._embeddings, example.question, answer)
        context_recall = _compute_context_recall(example.ground_truth, contexts)
        retrieval_hit_at_k = _compute_retrieval_hit_at_k(example, retrieved_docs)
        section_match_rate = _compute_section_match_rate(example, retrieved_docs)
        citation_coverage = _compute_citation_coverage(example, citations)

        return EvalResult(
            id=example.id,
            question=example.question,
            answer=answer,
            ground_truth=example.ground_truth,
            faithfulness=faithfulness,
            answer_relevancy=answer_relevancy,
            context_recall=context_recall,
            retrieval_hit_at_k=retrieval_hit_at_k,
            section_match_rate=section_match_rate,
            citation_coverage=citation_coverage,
            retrieved_count=len(contexts),
            query_type=query_type,
            latency_sec=latency,
            error=error,
        )

    def run(
        self,
        examples: Optional[List[EvalExample]] = None,
        run_name: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if examples is None:
            examples = self.load_dataset()

        mlflow.set_experiment(self.experiment_name)

        with mlflow.start_run(run_name=run_name):
            if params:
                mlflow.log_params(params)
            mlflow.log_param("n_questions", len(examples))

            results: List[EvalResult] = []
            for index, example in enumerate(examples, 1):
                logger.info("Evaluating [%s/%s] %s", index, len(examples), example.id)
                result = self.evaluate_one(example)
                results.append(result)
                mlflow.log_metrics(
                    {
                        "faithfulness": result.faithfulness,
                        "answer_relevancy": result.answer_relevancy,
                        "context_recall": result.context_recall,
                        "retrieval_hit_at_k": result.retrieval_hit_at_k,
                        "section_match_rate": result.section_match_rate,
                        "citation_coverage": result.citation_coverage,
                        "latency_sec": result.latency_sec,
                    },
                    step=index,
                )

            valid_results = [result for result in results if result.error is None]
            error_rate = (len(results) - len(valid_results)) / len(results) if results else 0.0

            def _average(attr: str) -> float:
                values = [getattr(result, attr) for result in valid_results]
                return float(np.mean(values)) if values else 0.0

            aggregate = {
                "faithfulness": _average("faithfulness"),
                "answer_relevancy": _average("answer_relevancy"),
                "context_recall": _average("context_recall"),
                "retrieval_hit_at_k": _average("retrieval_hit_at_k"),
                "section_match_rate": _average("section_match_rate"),
                "citation_coverage": _average("citation_coverage"),
                "avg_score": _average("aggregate_score"),
                "avg_latency": _average("latency_sec"),
                "error_rate": error_rate,
            }
            mlflow.log_metrics({"agg_" + key: value for key, value in aggregate.items()})

            artifact_path = _PROJECT_ROOT / "mlruns" / "_eval_artifact_tmp.json"
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            with open(artifact_path, "w", encoding="utf-8") as file:
                json.dump(
                    [
                        {
                            "id": result.id,
                            "question": result.question,
                            "answer": result.answer[:500],
                            "faithfulness": result.faithfulness,
                            "answer_relevancy": result.answer_relevancy,
                            "context_recall": result.context_recall,
                            "retrieval_hit_at_k": result.retrieval_hit_at_k,
                            "section_match_rate": result.section_match_rate,
                            "citation_coverage": result.citation_coverage,
                            "latency_sec": result.latency_sec,
                            "query_type": result.query_type,
                            "error": result.error,
                        }
                        for result in results
                    ],
                    file,
                    ensure_ascii=False,
                    indent=2,
                )
            mlflow.log_artifact(str(artifact_path), artifact_path="eval_results")
            artifact_path.unlink(missing_ok=True)

            logger.info(
                "\n=== Evaluation complete (%s questions) ===\n"
                "  Faithfulness     : %.3f\n"
                "  Answer Relevancy : %.3f\n"
                "  Context Recall   : %.3f\n"
                "  Retrieval Hit@k  : %.3f\n"
                "  Section Match    : %.3f\n"
                "  Citation Coverage: %.3f\n"
                "  Avg Score        : %.3f\n"
                "  Error Rate       : %.1f%%",
                len(results),
                aggregate["faithfulness"],
                aggregate["answer_relevancy"],
                aggregate["context_recall"],
                aggregate["retrieval_hit_at_k"],
                aggregate["section_match_rate"],
                aggregate["citation_coverage"],
                aggregate["avg_score"],
                aggregate["error_rate"] * 100,
            )

        return {"aggregate": aggregate, "per_question": results}


if __name__ == "__main__":
    import glob
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    sys.path.insert(0, str(_PROJECT_ROOT / "src"))
    from agent.financial_graph import FinancialAgent
    from processing.financial_parser import FinancialParser
    from storage.vector_store import VectorStoreManager

    chroma_path = str(_PROJECT_ROOT / "data" / "chroma_dart")
    vsm = VectorStoreManager(persist_directory=chroma_path, collection_name=DEFAULT_COLLECTION_NAME)

    if len(vsm.bm25_docs) == 0:
        print("[INFO] ChromaDB is empty. Indexing local filings first...")
        reports = glob.glob(str(_PROJECT_ROOT / "data" / "reports" / "**" / "*.html"), recursive=True)
        if not reports:
            print("[ERROR] No .html file found under data/reports/. Run dart_fetcher.py first.")
            sys.exit(1)

        parser = FinancialParser(chunk_size=1500, chunk_overlap=200)
        agent_tmp = FinancialAgent(vsm)
        for file_path in reports:
            parts = Path(file_path).stem.split("_")
            metadata = {
                "company": Path(file_path).parent.name,
                "stock_code": "unknown",
                "year": int(parts[0]) if parts[0].isdigit() else 2023,
                "report_type": parts[1] if len(parts) > 1 else "사업보고서",
                "rcept_no": parts[-1] if len(parts) > 2 else "unknown",
            }
            chunks = parser.process_document(file_path, metadata)
            agent_tmp.ingest(chunks)
            print(f"  indexed: {Path(file_path).name} ({len(chunks)} chunks)")
    else:
        print(f"[INFO] Using existing ChromaDB with {len(vsm.bm25_docs)} chunks")

    agent = FinancialAgent(vsm, k=8)
    evaluator = RAGEvaluator(agent)

    dataset = evaluator.load_dataset()
    smoke_set = evaluator.build_single_company_eval_slice(dataset, max_questions=5)

    print(f"\n=== RAGEvaluator smoke test ({len(smoke_set)} questions) ===\n")
    results = evaluator.run(
        examples=smoke_set,
        run_name="single_company_smoke_test",
        params={
            "chunk_size": 1500,
            "k": 8,
            "strategy": "hybrid_rerank",
            "embedding_model": DEFAULT_EMBEDDING_MODEL,
            "collection_name": DEFAULT_COLLECTION_NAME,
        },
    )

    print("\n[Per-question]")
    for result in results["per_question"]:
        print(
            f"  {result.id:15s} | F={result.faithfulness:.2f} "
            f"R={result.answer_relevancy:.2f} C={result.context_recall:.2f} "
            f"Hit@k={result.retrieval_hit_at_k:.2f} "
            f"Sec={result.section_match_rate:.2f} "
            f"Cite={result.citation_coverage:.2f} "
            f"| {result.latency_sec:.1f}s"
            + (f" ERROR: {result.error}" if result.error else "")
        )

    aggregate = results["aggregate"]
    print(
        "\nAggregate: "
        f"Faithfulness={aggregate['faithfulness']:.3f}, "
        f"Relevancy={aggregate['answer_relevancy']:.3f}, "
        f"Recall={aggregate['context_recall']:.3f}, "
        f"Hit@k={aggregate['retrieval_hit_at_k']:.3f}, "
        f"Section={aggregate['section_match_rate']:.3f}, "
        f"Citation={aggregate['citation_coverage']:.3f}, "
        f"Avg={aggregate['avg_score']:.3f}"
    )
    print("\nMLflow UI: mlflow ui --backend-store-uri mlruns/")
