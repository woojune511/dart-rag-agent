"""
RAG 평가 파이프라인.

3가지 지표를 측정하고 MLflow로 실험을 추적:
  - Faithfulness    : 답변이 검색된 컨텍스트에만 근거하는가 (LLM-as-judge, 0~1)
  - Answer Relevancy: 질문과 답변의 의미 유사도 (임베딩 코사인, 0~1)
  - Context Recall  : 정답 핵심 키워드가 컨텍스트에 포함되는가 (키워드 recall, 0~1)

사용법:
    evaluator = RAGEvaluator(agent)
    results = evaluator.run(run_name="baseline", params={"chunk_size": 1500, "k": 8})
    print(results["aggregate"])
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import mlflow
import numpy as np
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DATASET = _PROJECT_ROOT / "data" / "eval" / "eval_dataset.json"


# --------------------------------------------------------------------------
# 데이터 모델
# --------------------------------------------------------------------------

@dataclass
class EvalExample:
    id: str
    question: str
    ground_truth: str
    company: str
    year: int
    section: str


@dataclass
class EvalResult:
    id: str
    question: str
    answer: str
    ground_truth: str
    faithfulness: float       # LLM judge: 0.0 ~ 1.0
    answer_relevancy: float   # 임베딩 코사인: 0.0 ~ 1.0
    context_recall: float     # 키워드 recall: 0.0 ~ 1.0
    retrieved_count: int
    query_type: str
    latency_sec: float
    error: Optional[str] = None

    @property
    def aggregate_score(self) -> float:
        """3지표 단순 평균."""
        return (self.faithfulness + self.answer_relevancy + self.context_recall) / 3.0


# --------------------------------------------------------------------------
# 지표 계산
# --------------------------------------------------------------------------

_FAITHFULNESS_PROMPT = """\
다음은 검색된 컨텍스트와 그에 대한 답변입니다.
답변이 컨텍스트에서만 근거한 정보를 담고 있는지 평가해주세요.

[컨텍스트]
{context}

[답변]
{answer}

평가 기준:
- 1.0: 답변의 모든 내용이 컨텍스트에 명확히 근거함
- 0.7: 대부분 근거하지만 일부 추론/일반 상식이 포함됨
- 0.5: 절반 정도는 컨텍스트 기반, 나머지는 외부 지식
- 0.3: 컨텍스트와 관련은 있으나 대부분 외부 지식에 의존
- 0.0: 컨텍스트와 무관한 답변

숫자(0.0~1.0)만 응답하세요. 설명 없이 점수만 출력합니다."""


def _compute_faithfulness(
    llm: ChatGoogleGenerativeAI,
    answer: str,
    contexts: List[str],
) -> float:
    """LLM-as-judge: 답변이 컨텍스트에 충실한가."""
    if not answer or not contexts:
        return 0.0

    context_text = "\n\n---\n\n".join(contexts[:5])   # 상위 5개만 사용 (토큰 절약)
    prompt = _FAITHFULNESS_PROMPT.format(context=context_text[:4000], answer=answer[:1500])

    try:
        response = llm.invoke(prompt)
        text = response.content.strip()
        # 응답에서 0.0~1.0 숫자 추출
        match = re.search(r"(0(?:\.\d+)?|1(?:\.0+)?)", text)
        return float(match.group(1)) if match else 0.5
    except Exception as e:
        logger.warning(f"faithfulness 계산 실패: {e}")
        return 0.5


def _compute_answer_relevancy(
    embeddings: HuggingFaceEmbeddings,
    question: str,
    answer: str,
) -> float:
    """질문-답변 임베딩 코사인 유사도."""
    if not answer:
        return 0.0
    try:
        q_vec = np.array(embeddings.embed_query(question))
        a_vec = np.array(embeddings.embed_query(answer))
        cos = np.dot(q_vec, a_vec) / (np.linalg.norm(q_vec) * np.linalg.norm(a_vec) + 1e-9)
        return float(np.clip(cos, 0.0, 1.0))
    except Exception as e:
        logger.warning(f"answer_relevancy 계산 실패: {e}")
        return 0.5


def _tokenize_ko(text: str) -> set[str]:
    """한국어 텍스트를 어절/숫자 단위로 토큰화 (단순 공백+구두점 분리)."""
    tokens = re.findall(r"[가-힣a-zA-Z0-9]+", text)
    # 2글자 이상 토큰만 유효 (조사 등 제거)
    return {t for t in tokens if len(t) >= 2}


def _compute_context_recall(
    ground_truth: str,
    contexts: List[str],
) -> float:
    """
    정답의 핵심 키워드가 검색된 컨텍스트에 얼마나 포함되는가.

    정답을 문장 단위로 분리 → 문장 내 핵심 토큰 추출 →
    어느 컨텍스트에서든 해당 토큰이 등장하는 비율로 recall 계산.
    """
    if not ground_truth or not contexts:
        return 0.0

    context_all = " ".join(contexts)
    context_tokens = _tokenize_ko(context_all)

    # 정답을 문장 단위로 분리
    sentences = re.split(r"[.。\n]", ground_truth)
    sentences = [s.strip() for s in sentences if len(s.strip()) >= 6]
    if not sentences:
        return 0.0

    covered = 0
    for sent in sentences:
        sent_tokens = _tokenize_ko(sent)
        if not sent_tokens:
            continue
        # 문장 토큰 중 절반 이상이 컨텍스트에 등장하면 "커버됨"으로 간주
        overlap = sent_tokens & context_tokens
        if len(overlap) / len(sent_tokens) >= 0.5:
            covered += 1

    return covered / len(sentences)


# --------------------------------------------------------------------------
# 평가기 메인 클래스
# --------------------------------------------------------------------------

class RAGEvaluator:
    """
    RAG 파이프라인 품질 평가기.

    Args:
        agent: FinancialAgent 인스턴스 (agent.run(query) → dict 지원)
        dataset_path: 평가 데이터셋 JSON 경로 (기본: data/eval/eval_dataset.json)
        experiment_name: MLflow 실험 이름
    """

    def __init__(
        self,
        agent,
        dataset_path: Optional[str] = None,
        experiment_name: str = "dart_rag_eval",
    ):
        self.agent = agent
        self.experiment_name = experiment_name
        self._dataset_path = Path(dataset_path) if dataset_path else _DEFAULT_DATASET

        # 지표 계산용 LLM / 임베딩
        self._llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.0,
        )
        # answer_relevancy: vector_store와 동일 모델로 일관성 유지
        self._embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    # ------------------------------------------------------------------
    # 데이터셋 로드
    # ------------------------------------------------------------------

    def load_dataset(self) -> List[EvalExample]:
        """JSON 평가셋 로드."""
        with open(self._dataset_path, encoding="utf-8") as f:
            data = json.load(f)
        return [
            EvalExample(
                id=d["id"],
                question=d["question"],
                ground_truth=d["ground_truth"],
                company=d["company"],
                year=d["year"],
                section=d["section"],
            )
            for d in data
        ]

    # ------------------------------------------------------------------
    # 단일 예제 평가
    # ------------------------------------------------------------------

    def evaluate_one(self, example: EvalExample) -> EvalResult:
        """단일 질문에 대해 agent 실행 후 3가지 지표 계산."""
        t0 = time.time()
        error = None
        answer = ""
        contexts: List[str] = []
        query_type = "unknown"

        try:
            result = self.agent.run(example.question)
            answer = result.get("answer", "")
            query_type = result.get("query_type", "unknown")
            # retrieved_docs는 (DocumentChunk, score) 튜플 리스트
            raw_docs = result.get("retrieved_docs", [])
            contexts = []
            for item in raw_docs:
                doc = item[0] if isinstance(item, (tuple, list)) else item
                text = doc.content if hasattr(doc, "content") else doc.page_content
                contexts.append(text)
        except Exception as e:
            error = str(e)
            logger.error(f"[{example.id}] agent.run 실패: {e}")

        latency = time.time() - t0

        # 지표 계산
        faithfulness = _compute_faithfulness(self._llm, answer, contexts)
        relevancy = _compute_answer_relevancy(self._embeddings, example.question, answer)
        recall = _compute_context_recall(example.ground_truth, contexts)

        return EvalResult(
            id=example.id,
            question=example.question,
            answer=answer,
            ground_truth=example.ground_truth,
            faithfulness=faithfulness,
            answer_relevancy=relevancy,
            context_recall=recall,
            retrieved_count=len(contexts),
            query_type=query_type,
            latency_sec=latency,
            error=error,
        )

    # ------------------------------------------------------------------
    # 전체 평가 실행 + MLflow 로깅
    # ------------------------------------------------------------------

    def run(
        self,
        examples: Optional[List[EvalExample]] = None,
        run_name: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        평가 실행 및 MLflow 로깅.

        Args:
            examples: 평가할 예제 목록 (None이면 전체 데이터셋)
            run_name: MLflow run 이름
            params: MLflow에 기록할 실험 파라미터 (chunk_size, k 등)

        Returns:
            {
                "aggregate": {"faithfulness": float, "answer_relevancy": float,
                              "context_recall": float, "avg_score": float,
                              "avg_latency": float, "error_rate": float},
                "per_question": [EvalResult, ...],
            }
        """
        if examples is None:
            examples = self.load_dataset()

        mlflow.set_experiment(self.experiment_name)

        with mlflow.start_run(run_name=run_name):
            # 파라미터 로깅
            if params:
                mlflow.log_params(params)
            mlflow.log_param("n_questions", len(examples))

            results: List[EvalResult] = []
            for i, ex in enumerate(examples, 1):
                logger.info(f"평가 중 [{i}/{len(examples)}] {ex.id}: {ex.question[:50]}")
                res = self.evaluate_one(ex)
                results.append(res)

                # 개별 질문 지표 로깅 (MLflow metric step = 질문 순서)
                mlflow.log_metrics(
                    {
                        "faithfulness":     res.faithfulness,
                        "answer_relevancy": res.answer_relevancy,
                        "context_recall":   res.context_recall,
                        "latency_sec":      res.latency_sec,
                    },
                    step=i,
                )

            # 집계 지표 계산
            valid = [r for r in results if r.error is None]
            error_rate = (len(results) - len(valid)) / len(results) if results else 0.0

            def _avg(attr: str) -> float:
                vals = [getattr(r, attr) for r in valid]
                return float(np.mean(vals)) if vals else 0.0

            aggregate = {
                "faithfulness":     _avg("faithfulness"),
                "answer_relevancy": _avg("answer_relevancy"),
                "context_recall":   _avg("context_recall"),
                "avg_score":        _avg("aggregate_score"),
                "avg_latency":      _avg("latency_sec"),
                "error_rate":       error_rate,
            }
            mlflow.log_metrics({"agg_" + k: v for k, v in aggregate.items()})

            # 상세 결과를 아티팩트로 저장
            artifact_path = _PROJECT_ROOT / "mlruns" / "_eval_artifact_tmp.json"
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            with open(artifact_path, "w", encoding="utf-8") as f:
                json.dump(
                    [
                        {
                            "id": r.id,
                            "question": r.question,
                            "answer": r.answer[:500],
                            "faithfulness": r.faithfulness,
                            "answer_relevancy": r.answer_relevancy,
                            "context_recall": r.context_recall,
                            "latency_sec": r.latency_sec,
                            "query_type": r.query_type,
                            "error": r.error,
                        }
                        for r in results
                    ],
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            mlflow.log_artifact(str(artifact_path), artifact_path="eval_results")
            artifact_path.unlink(missing_ok=True)

            logger.info(
                f"\n=== 평가 완료 ({len(results)}문항) ===\n"
                f"  Faithfulness    : {aggregate['faithfulness']:.3f}\n"
                f"  Answer Relevancy: {aggregate['answer_relevancy']:.3f}\n"
                f"  Context Recall  : {aggregate['context_recall']:.3f}\n"
                f"  Avg Score       : {aggregate['avg_score']:.3f}\n"
                f"  Error Rate      : {aggregate['error_rate']:.1%}"
            )

        return {"aggregate": aggregate, "per_question": results}


# --------------------------------------------------------------------------
# 스모크 테스트
# --------------------------------------------------------------------------

if __name__ == "__main__":
    import glob
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # agent 초기화
    sys.path.insert(0, str(_PROJECT_ROOT / "src"))
    from storage.vector_store import VectorStoreManager
    from agent.financial_graph import FinancialAgent
    from processing.financial_parser import FinancialParser

    chroma_path = str(_PROJECT_ROOT / "data" / "chroma_dart")
    vsm = VectorStoreManager(persist_directory=chroma_path, collection_name="dart_reports")

    # ChromaDB에 문서가 없으면 먼저 인덱싱
    if len(vsm.bm25_docs) == 0:
        print("[INFO] ChromaDB 비어있음 — 문서 인덱싱 중...")
        reports = glob.glob(str(_PROJECT_ROOT / "data" / "reports" / "**" / "*.html"), recursive=True)
        if not reports:
            print("[ERROR] data/reports/ 에 .html 파일 없음. dart_fetcher.py 먼저 실행하세요.")
            sys.exit(1)

        parser = FinancialParser(chunk_size=1500, chunk_overlap=200)
        agent_tmp = FinancialAgent(vsm)
        for fp in reports:
            parts = Path(fp).stem.split("_")
            meta = {
                "company":     Path(fp).parent.name,
                "stock_code":  "unknown",
                "year":        int(parts[0]) if parts[0].isdigit() else 2023,
                "report_type": parts[1] if len(parts) > 1 else "사업보고서",
                "rcept_no":    parts[-1] if len(parts) > 2 else "unknown",
            }
            chunks = parser.process_document(fp, meta)
            agent_tmp.ingest(chunks)
            print(f"  인덱싱 완료: {Path(fp).name} ({len(chunks)}청크)")
    else:
        print(f"[INFO] ChromaDB 기존 문서 {len(vsm.bm25_docs)}개 청크 사용")

    agent = FinancialAgent(vsm, k=8)
    evaluator = RAGEvaluator(agent)

    # 빠른 스모크: 리스크 관련 3문항만 실행
    dataset = evaluator.load_dataset()
    smoke_set = [ex for ex in dataset if ex.section in ("리스크", "경영진단")][:3]

    print(f"\n=== RAGEvaluator 스모크 테스트 ({len(smoke_set)}문항) ===\n")
    results = evaluator.run(
        examples=smoke_set,
        run_name="smoke_test",
        params={"chunk_size": 1500, "k": 8, "strategy": "hybrid"},
    )

    print("\n[문항별 결과]")
    for r in results["per_question"]:
        print(
            f"  {r.id:15s} | F={r.faithfulness:.2f} "
            f"R={r.answer_relevancy:.2f} C={r.context_recall:.2f} "
            f"| {r.latency_sec:.1f}s"
            + (f" ERROR: {r.error}" if r.error else "")
        )

    agg = results["aggregate"]
    print(f"\n집계: Faithfulness={agg['faithfulness']:.3f}, "
          f"Relevancy={agg['answer_relevancy']:.3f}, "
          f"Recall={agg['context_recall']:.3f}, "
          f"Avg={agg['avg_score']:.3f}")
    print("\nMLflow UI: mlflow ui --backend-store-uri mlruns/")