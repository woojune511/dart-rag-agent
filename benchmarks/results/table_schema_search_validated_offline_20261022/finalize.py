"""Record bounded source review and close this diagnostic without another treatment."""
import json
from collections import Counter

from run import ARMS, OUT, ROOT, prior, preserve, save

summary = prior.load(OUT / "automated_summary.json")
audit = prior.load(OUT / "all77_source_audit.json")["cases"]
panel = prior.load(OUT / "known_witness_panel.json")
results = {r["case_id"]: r for r in prior.load(OUT / "results.json")}
packets = {(cid, arm): prior.load(OUT / "packets" / f"{cid}_{arm}.json") for cid in results for arm in ARMS}


def witness(cid, arm, uid, quote):
    d = next(d for d in packets[cid, arm]["documents"] if d["chunk_id"] == uid)
    assert quote in d["text"], (cid, arm, uid, quote)
    return {"case_id": cid, "arm": arm, "uid": uid, "quote": quote,
            "offset": d["text"].index(quote), "source_text_sha256": prior.text_sha(d["text"])}


facts = [
    witness("HYU_T3_072", "S12", "20240313001451:275:133", "Motional AD LLC (*1,5) | 자율주행 소프트웨어 개발 | 미국 | 26% | 700,691"),
    witness("HYU_T3_072", "S12", "20240313001451:275:133", "[unit_hint: 백만원]"),
    witness("SKI_T1_068", "S12", "20240320000950:882:499", "810,900 | 516,482 | 997,795 | (581,816)"),
    witness("SKI_T1_068", "S12", "20240320000950:882:499", "[unit_hint: 백만원]"),
    witness("MIX_T3_048", "A12", "20240312000736:127:6", "배당금의 지급 | (9,864,474)"),
    witness("MIX_T3_048", "S12", "20240312000736:383:4", "배당금의 지급 | (9,810,119)"),
    witness("MIX_T3_048", "S12", "20240312000736:590:0", "2024년부터 2026년까지 3년간 발생하는 잉여현금흐름의 50%"),
    witness("HYU_T2_010", "A12", "20240313001451:96:5", "2023년 미국시장에서 현대차는 전년 대비 11.5% 증가한 87.0만 대"),
    witness("HYU_T2_010", "A12", "20240313001451:96:5", "2022년에는 전년 대비 0.9% 감소한 78.1만 대"),
    witness("HYU_T2_010", "S12", "20240313001451:1058:14", "미국의 인플레이션 감축법과 유럽의 핵심원자재법"),
    witness("HYU_T2_010", "S12", "20240313001451:47:7", "금융상품판매대리·중개업"),
    witness("KBF_T2_018", "S12", "20240326000894:1846:5", "신용손실충당금전입액은 미래경기 불확실성에 대비한 보수적인 충당금적립으로"),
    witness("HYU_T3_011", "S12", "20240313001451:1047:3", "자동차 판매물량 증가로 매출액이 전년 대비 14.8% 증가"),
    witness("HYU_T3_011", "S12", "20240313001451:1047:3", "GV70, GV80 등 고급차 및 SUV 판매증가 영향 믹스개선"),
    witness("MIX_T2_047", "S12", "20240313001451:1045:1", "글로벌 누적판매 100만대를 돌파"),
    witness("KBF_T3_019", "S12", "20240326000894:1885:44", "총 PF대출 약정한도는 56,206억원, 실행잔액은 40,020억원"),
    witness("LGE_T2_052", "A12", "20240314001110:20:1", "(단위 : USD)"),
    witness("LGE_T2_052", "S12", "20240314001110:21:2", "전동공구용 배터리 | 1.89 | 1.62 | 1.28"),
    witness("LGE_T2_052", "S12", "20240314001110:897:3", "배터리 판매가격 대비 투입 원재료비가 높아서 발생하는 Lagging 영향"),
    witness("NAV_T3_032", "S12", "20240318000844:40:4", "CapEx | 692.3 | 756.2"),
    witness("CEL_T2_014", "S12", "20240318000913:103:44", "CT-P47 | Rheumatoid Arthritis"),
    witness("CEL_T3_015", "S12", "20240318000913:969:372", "2023년 12월 28일을 합병기일로 셀트리온헬스케어를 흡수합병"),
    witness("CEL_T3_015", "S12", "20240318000913:575:415", "개발-생산-판매 일원화를 통한 제품력 및 원가경쟁력 확보"),
    witness("KAB_T3_067", "S12", "20240320001487:82:21", "2023년 7월에는 펀드투자 라이선스를 획득"),
]

notes = {
    "KBF_T2_018": ("PRIMARY_EVIDENCE_RETAINED_SUPPORT_DETAIL_LOST", "전입액과 직접 원인 1846:5는 유지. worse/crisis 보충 설명 662:19는 사라짐. 주원인 전체 누락으로 세지 않음."),
    "MIX_T3_048": ("REQUIRED_EVIDENCE_LOST", "연결 실제 지급액 9,864,474백만원이 빠지고 별도 지급액 9,810,119와 선언배당 등이 남음. 환원정책은 유지. 단위·범위가 다른 수치로 대체할 수 없음."),
    "HYU_T2_010": ("FIXED_PANEL_EVIDENCE_LOST_BENCHMARK_HOLD", "현대차 2023/2022 미국 판매 87.0/78.1만대가 빠짐. IRA 대응은 유지. 질문 주체 생략에 대한 기존 benchmark HOLD와 별개로, 고정 진단 패널의 현대차 해석에 필요한 근거가 사라짐."),
    "HYU_T3_011": ("PRIMARY_EVIDENCE_RETAINED", "1045:1의 재료비 개선 등 설명이 빠졌으나 MD&A 1047:3의 물량 증가 및 고급차/SUV 믹스 개선 두 원인은 유지."),
    "MIX_T2_047": ("PRIMARY_EVIDENCE_RETAINED", "GV60 유럽 수상·브랜드관리 상세가 줄었으나 1045:1의 고부가 믹스·누적100만대와 103:12의 브랜드 전략은 유지."),
    "KBF_T3_019": ("ALTERNATIVE_SOURCE_RETAINED", "1111:468의 책임준공·약정한도·실행잔액 내용은 1885:44 및 2140:45에도 남아 있음. 인용 UID 손실을 근거 전체 손실로 세지 않음."),
    "LGE_T2_052": ("PRODUCT_PRICE_UNIT_CONTEXT_LOST", "원재료 표 24:2/23:1과 Lagging 설명 897:3은 유지. 제품가격 21:2의 1.89/1.62는 남지만 그 표의 USD 표제 20:1이 빠짐. 다른 원재료 표의 USD를 자동 연결하지 않음. 답변 오류 자체는 미측정."),
    "NAV_T3_032": ("PRIMARY_EVIDENCE_RETAINED_QUALIFIER_LOST", "연결 CAPEX 692.3십억원, 세종/춘천/클라우드 투자 설명은 40:4에 유지. 별도 주석의 취득·자본적지출 세부 설명 1238:137은 손실."),
    "CEL_T2_014": ("PRIMARY_PIPELINE_EVIDENCE_RETAINED", "108:49의 개별 CT-P47 표는 사라졌지만 103:44의 품목별 심사 상태와 기준일 이후 US/EU/한국 신청 표시 및 1056:11의 파이프라인 개요는 유지. 모든 상세 표현의 동일성을 주장하지 않음."),
    "CEL_T3_015": ("PRIMARY_EVIDENCE_RETAINED_EXTRA_DISCLOSURES_LOST", "합병일·승인 사실은 969:372/1023:5, 목적은 연결 주석 575:415에 유지. 추가 파생상품·거래주석은 감소. 주석 범위 차이를 무시한 숫자 대체는 하지 않음."),
    "CEL_T3_040": ("PRIMARY_CONNECTED_VALUES_RETAINED", "연결 gross 평가손실/환입/폐기손실 517:357은 유지. 별도 상세 917:320은 빠지고 다른 표 518:358이 추가. 기본 필수 세 금액의 손실은 아님."),
    "KAB_T3_067": ("PRIMARY_EVIDENCE_RETAINED", "173:77 두 수수료, 54:18 서비스, 82:21의 2023 세금신고·펀드 라이선스 및 300:6 조직개편 유지. 295:1의 경영진 서술 감소는 별도로 기록."),
}
reviews = []
for a in audit:
    lost = a["arms"]["S12"]["historical_cited_sources_lost"]
    if not lost:
        continue
    cid = a["case_id"]
    if cid in notes:
        status, note = notes[cid]
    elif a["historical_group"] == "refusal":
        status, note = "REFUSAL_NOT_EVALUATED", "인용하던 자료가 교체됨. 새 답변 없이 거절 성공/실패를 판정하지 않음."
    else:
        assert a["historical_group"] == "diagnostic_or_hold"
        status, note = "HOLD_SOURCE_CHANGE_UNRESOLVED", "기존 HOLD의 범위·해석 모호성을 유지. 관련 출처 감소를 기록하되 정확도 회귀로 계산하지 않음."
    reviews.append({"case_id": cid, "historical_group": a["historical_group"], "lost_citations": lost,
                    "finding": status, "note": note})
assert len(reviews) == 20

source_review = {"reviewer": "same assistant, source-grounded but not blinded or independent",
                 "scope": "All77 mechanical source audit; all20 S12 historical citation-loss cases triaged; fixed10-answerable/26-unit panel and identified recoveries inspected. No full77 new semantic answer grading.",
                 "citation_loss_groups": dict(Counter(r["historical_group"] for r in reviews)),
                 "cases": reviews, "verified_quote_witnesses": facts}
save("source_review.json", source_review)
preservation = preserve()
execution = prior.load(OUT / "execution_result.json")
execution.update({"status": "COMPLETE_NOT_ADOPTED", "verification_status": "PARTIAL: local retrieval/provenance and bounded source review verified; answer quality and generalization untested",
                  "focused_tests_passed": 10, "focused_tests_failed": 0,
                  "command": ".venv\\Scripts\\python.exe -B -X utf8 benchmarks/results/table_schema_search_validated_offline_20261022/run.py run",
                  "exit_code": 0, "valid_completed_policy_runs": 1,
                  "invalidated_prior_run": "benchmarks/results/table_schema_search_offline_20261022/validity.json",
                  "preservation": preservation})
save("execution_result.json", execution)
review = {"status": "COMPLETE_NOT_ADOPTED", "decision": "현재 일괄 혼합 정책 S12는 채택하지 않음. 기존 후보의 일부 순위 개선은 있으나 새 필수근거 후보 복구는 진단 패널에서 확인되지 않았고, 기준선 A12의 필수근거 및 단위 문맥 손실이 발생. 이 결과는 모든 표 스키마 접근의 반증이 아님.",
          "origin_skill": "experiment-agent", "mode": "run", "verification_status": "PARTIAL",
          "date": "2026-10-22", "summary": summary["arms"], "source_review": source_review,
          "catalog": prior.load(OUT / "catalog_admission.json"), "row_units": prior.load(OUT / "row_unit_completeness.json"),
          "baseline_parity": prior.load(OUT / "baseline_parity.json"), "execution": execution,
          "facts": ["A8/A12 saved packet equality holds for every one of77 questions; original BM25 maximum score difference0.",
                    "63367 admitted numeric rows form6523 table schemas;43521 row-unit occurrences retained.",
                    "HYU275 and SKI882 were already in the original candidate union. Their inclusion is selection recovery, not evidence of new candidate recall.",
                    "All arms have24/26 known-witness candidate hits in the frozen10-case panel; S12 final packet21/26 vs A12 24/26.",
                    "Samsung cashflow table was located at schema rank4 but ended RRF13; Hyundai US-sales prose RRF11->23. Neither loss is caused by byte truncation.",
                    "The reused Korean tokenizer gives a positive 매대 match for 판매대수 and 금융상품판매대리. Exact term contributions are saved; no token exceptions added."],
          "hypotheses_not_proven": ["Uniform schema allocation can favor lexical coincidences and divert final slots from a multi-part request's complementary evidence.",
                                     "Using hierarchy/relations and explicit request coverage may help; no such mechanism or new-report test was run here."],
          "limits": ["Existing77 are development-exposed; no new-report holdout or answer generation.",
                     "Only10 answerable cases have this frozen26-unit evidence panel;77 is not the semantic-evaluation denominator.",
                     "Structural validation rechecks persisted source rows/headers and original HTML hashes, not a fresh independent audit of every original HTML table axis.",
                     "Catalog admission inherits numeric-row and projected-column exclusions. Non-numeric tables and all ancestor table-group titles are not exhaustively represented.",
                     "S12 combines schema representation and frozen stream allocation. Their causal effects were not isolated.",
                     "D12 deepens lexical search only; saved Dense16 cannot be expanded in this no-call probe.",
                     "No inference of new answer accuracy, faithfulness, refusal quality, or production readiness."],
          "next_gate": "기준선 유지. 현재 가중치/쿼터를 반복 조정하지 않음. 후속 연구는 기존 필수근거를 보존하며 별도 요청 항목의 근거를 선택하는 문제를 새 보고서 고정 평가에서 검증해야 하며, 이번에는 실행하지 않음."}
save("review.json", review)

lines = [
    "# 표 검색 스키마 검증 결과", "",
    "표 스키마는 일부 값 표를 최종 문맥으로 올렸지만, 이번 일괄 혼합 정책은 채택하지 않는다. 기존 문맥12개보다 필수근거 보존이 낮아졌다. 앱 소스·설정·store는 변경하지 않았다.", "",
    "기존77문항의 저장된 Dense 후보와 원문을 재사용했다. 모델 API0회, 비용$0, 답변 생성0회다. 아래 근거 평가는 그중 사전에 근거 기준이 고정된10개 답변 가능 문항·26항목에 한정한다. 별도2개 거절 통제 문항은 답변 없이 거절 성공률을 매기지 않았다.", "",
    "| 조건 | 최종 문맥 상한 | 필수근거의 확인된 출처 포함 | 모든 필수근거 포함 문항 | 평균 문맥 bytes |",
    "|---|---:|---:|---:|---:|",
]
labels = {"A8": "기존 검색", "A12": "기존 검색", "D12": "원문 BM25 후보24→48", "S12": "표 스키마 혼합"}
for arm in ARMS:
    s = summary["arms"][arm]
    k = 8 if arm == "A8" else 12
    panel_count = s["packet_known_witness_panel"]
    lines.append(f"| {labels[arm]} | {k} | {panel_count['known_witness_unit_hits']}/26 | {panel_count['all_units_hit_cases']}/10 | {s['packet_mean_bytes']:,.1f} |")
lines += ["",
    "이 숫자는 정답률이 아니다. 기존 원문 증거와 이전에 확인한 대체 출처를 기준으로 문맥에 근거가 남았는지를 검사했다. 현대차 미국 판매 질문의 주체 모호성에 대한 기존 benchmark HOLD는 유지하며, 진단 패널에서는 미리 고정한 현대차 해석의 근거만 비교했다.", "",
    "**고정한 검색 조건**: 기존 Dense16, 동일 질문·보고서 범위, 기존 한국어 토큰화, equal RRF60, 문맥65,536 UTF-8 bytes를 유지했다. 스키마는 독립 BM25 색인에서 상위12개 표를 찾고 표당 최대2개 원래 청크를 조회한다. 원문 BM25 후보와 번갈아 중복을 제거해 하나의24개 lexical 후보 목록을 만든 뒤 기존 RRF에 넣는다. 원문과 스키마의 원점수를 직접 비교하거나 RRF 투표 채널을 추가하지 않았다. 표 내부 소유 청크 순서는 기존 원문 BM25 점수로 정했다.", "",
    "**스키마 입력과 연결 검사**:16,051개 원문 청크에서 이미 연결이 검증된 숫자 행63,367개를 재검사해 표6,523개로 묶었다. 행 이름·열 헤더·기존 절 경로·직접 확인되는 짧은 표제와 기간·단위를 사용했다. 수치 value 필드, 생성 요약, 동의어, 추정 연도는 색인에 넣지 않았다. 행 이름에 포함된 취득일 같은 숫자 문자열까지 제거한 것은 아니다. 행·셀·원래 열 위치·헤더·source locator와 원본 HTML 해시를 연결했고 답변 문맥에는 원래 청크 전체를 반환했다. 행별 단위43,521건은 모두 스키마 단위 필드에 남았다.", "",
    "**관측된 복구**: Motional 지분·장부금액 표는 RRF27→8위가 되어26%와700,691백만원이 들어왔다. 배터리 영업손실 표는15→11위가 되어(581,816)백만원과 열 헤더가 들어왔다. 두 표는 원래 후보 합집합에도 존재했다. 따라서 새 필수근거 후보를 찾아냈다는 결과가 아니라 최종 선택 복구다. Motional 요약손익 표는 여전히 빠져 질문 전체 해결로 세지 않는다.", "",
    "**확인된 손실**: 삼성전자 연결 실제 배당금 지급액 표는 스키마4위로 찾았지만 RRF10→13위로 밀려 빠졌다. 별도 지급액과 선언배당은 해당 값을 대신할 수 없다. 현대차 미국 판매87.0/78.1만대 문단은 RRF11→23위로 밀렸다. 두 경우 모두65,536-byte 제한 때문이 아니다. LG에너지솔루션 제품가격 값은 유지됐지만 그 표의 USD 표제는 빠져, 별도 원재료 표의 단위를 잘못 연결할 위험이 남는다.", "",
    "**77문항 점검**: A12 대비 S12의 출처 집합은66문항에서 달라졌고,20문항에서 과거 답변이 인용한 출처 일부가 사라졌다. 답변 가능11문항·기존HOLD5문항·거절4문항이다. 이는20건의 답변 오류를 뜻하지 않는다. 예를 들어 KB PF의 같은 내용은 다른 청크에 남았고, 현대차 수익성의 물량·믹스 원인도 유지됐다. 모든20건을 분류한 [출처 검토](source_review.json)와 [77문항 출처 감사](all77_source_audit.json)를 함께 보존했다. 이 범위 밖의 모든 대체 출처를 새로 의미 채점한 것은 아니다.", "",
    "**실패 층**: 고정 패널의 후보 단계는 모든 조건24/26으로 같다. 주요 손실은 최종 순위에서 발생했다. SK하이닉스 자산 표는 필요한 행 이름을 가지고도 스키마45위, Motional 요약손익 표는108위였다. 기존 BM25가 다중 요구를 하나의 점수로 합산하며, 판매대수와 금융상품판매대리에 공통된 매대 같은 문자 조각도 점수를 받는 것을 [동일 점수의 항별 분해](score_explanations.json)로 확인했다. 표 구조를 저장했다는 사실만으로 검색 점수가 행·열 관계나 요청 충족도를 이해하지는 않는다. 일괄 배분이 여러 요청 항목의 균형을 흐릴 수 있다는 해석은 이 관측에서 나온 가설이다.", "",
    "**실행 유효성**: 원문 BM25 순위와 점수, A8·A12의 저장 문맥을77문항 모두 정확히 재현했다. 경계 테스트10개가 통과했고 유효한 실행은약90.9초에 끝났다. 초기 해시 검사에서 HTML 대신 텍스트 추출본 경로를 확인한 오류를 수정했다. 첫 완료 실행은 행별 단위를 첫 행에서만 모으는 생성기 오류355건을 발견해 무효 처리했고, 별도 폴더에서 단위 수집만 바로잡아 재실행했다. 모델·가중치·할당 규칙을 결과에 맞춰 튜닝하지 않았다. 초기 산출물과 무효 사유도 보존했다.", "",
    "**범위와 종료**: 이번 결과는 기존 파서가 만든 숫자 행과 소유 청크에 한정된다. 텍스트 전용 표, 일부 열 투영 표, 모든 상위 TABLE-GROUP 제목을 빠짐없이 이용한 스키마가 아니며 원본 HTML의 모든 표 의미를 독립 재판정한 것도 아니다. S12는 스키마와 고정 혼합 배분을 함께 시험했으므로 스키마 표현만의 인과 효과는 분리하지 못했다. 새 보고서·새 답변·거절 성능은 미평가다. 현재 기준선을 유지하고 추가 튜닝은 종료한다. 후속 검증을 한다면 기존 필수근거를 밀어내지 않으면서 부족한 요청 항목의 근거를 선택하는 문제를 먼저 명확히 하고 새 보고서에서 평가해야 한다.", "",
    f"보존 검사: 기존 보호 파일{preservation['protected_files']:,}개의 SHA-256이 동일하다. .env·활성v12 store·기존 소스와 미커밋 파일·보호한 과거 실험 자료를 변경하지 않았으며 앱을 재시작하지 않았다. 이번 파일들은 ignored 실험 폴더에만 저장했고 commit/push하지 않았다.", "",
    "재현 자료: [사전 고정 조건](protocol.json), [실행 결과](execution_result.json), [근거 패널](known_witness_panel.json), [표별 순위](target_diagnostics.json), [기계 판독 결과](review.json), [보존 검사](preservation.json).", "",
]
(OUT / "report.md").write_text("\n".join(lines), encoding="utf-8")
print(prior.encoded({"decision": review["status"], "verified_quote_witnesses": len(facts), "citation_loss_cases_reviewed": len(reviews), "preserved_files": preservation["protected_files"]}))
