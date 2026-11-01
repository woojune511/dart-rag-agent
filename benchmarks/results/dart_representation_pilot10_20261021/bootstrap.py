"""Create the question lock before reading either new source."""
from pathlib import Path
import json, hashlib, shutil, subprocess
BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]

def write(name, value):
    with (BASE / name).open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, indent=2); f.write('\n')

for name in ('common.py', 'acquire.py'):
    text = (ROOT / 'benchmarks/results/new_report_user_eval_2026-10-15' / name).read_text('utf-8')
    if name == 'acquire.py':
        text = text.replace('Read three official public filings', 'Read two official public filings').replace("'20261015'", "'20261021'")
    with (BASE / name).open('x', encoding='utf-8', newline='\n') as f: f.write(text)
templates = [
    ('income', 'numeric', '{c}의 2025년 연결 기준 매출액과 영업이익을 제시하고, 영업이익률(영업이익 ÷ 매출액 × 100)을 소수 둘째 자리까지 계산해 줘. 금액 단위를 명시해 줘.'),
    ('inventory', 'numeric', '{c}의 2025년 말 연결 재무상태표 기준 재고자산 장부금액과 자산총계를 제시하고, 재고자산이 자산총계에서 차지하는 비율을 소수 둘째 자리까지 계산해 줘. 금액 단위를 명시해 줘.'),
    ('capex', 'numeric', '{c}의 2025년 연결 현금흐름표에 표시된 유형자산 취득 현금지출과 무형자산 취득 현금지출을 각각 제시하고 합계를 계산해 줘. 두 취득액은 지출 규모를 양수로 표시하고, 금액 단위를 명시해 줘.'),
    ('business', 'narrative', '{c}의 2025년 사업보고서에서 회사가 구분한 주요 사업부문과 각 부문의 대표 제품 또는 서비스를 요약해 줘.'),
    ('unanswerable', 'negative', '{c}의 2025년 12월 31일 하루 동안 발생한 연결 매출액은 얼마야? 연간 매출이나 일평균 매출로 대신하지 말고 그 날짜 하루의 실적을 알려줘.'),
]
companies = ['농심', '삼성전기']
questions = [{'id':f'{i+1:02d}_{kind}', 'company':c, 'kind':kind, 'type':t, 'query':q.format(c=c)} for i,c in enumerate(companies) for kind,t,q in templates]
write('question_seed.json', questions)
write('selection_lock.json', {'companies':companies, 'year':2025, 'as_of':'2026-10-21', 'selection':'Latest 2025.12 annual report per exact listed company, including corrections. No replacement after source inspection.', 'question_seed_sha256':hashlib.sha256((BASE/'question_seed.json').read_bytes()).hexdigest(), 'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(), 'model_calls_max':40, 'repeats':2, 'usd_total_cap':3})
write('pre_source_protocol.json', {
    'objective':'Small paired pilot of the complete DART representation pipeline against ordinary flat-text chunking; not a structure-only causal test.',
    'arms':{'generic':'lxml HTML text extraction preserving all visible text nodes; recursive 2500 character chunks with 320 overlap; common report metadata', 'dart':'Current local v12 FinancialParser, canonical structural selective v2 prefix 2500/320, source context metadata; no model preprocessing'},
    'fixed':{'model':'gpt-6.1-sol','reasoning':'low','max_output_tokens':8192,'embedding':'text-embedding-3-large','embedding_dimensions':3072,'retrieval':'Exact squared L2 dense top24 + BM25 positive top24; RRF60 final top12; same unmodified query; no expansion/reranker', 'context_max_bytes':65536, 'request_local_token_cap':12000, 'packet_policy':'Whole source only in ranked order; omit overflowing sources, do not truncate', 'generation':'Existing ANSWER_INSTRUCTIONS and RagAnswer schema, direct Responses harness, same wire for both arms'},
    'order':'Per question repeat1 generic then dart; repeat2 dart then generic. Embeddings once per corpus and shared query embeddings.',
    'evaluation':{'numeric':'Both requested operands, correct scope, unit, period and calculation; ratio tolerance 0.01 percentage point, amounts within half last displayed unit only; no contradictory material claim', 'narrative':'Required source-derived business segments and representative product or service per segment, no contradiction; rubric fixed before retrieval', 'negative':'Explicit insufficient daily evidence and abstained true; no fabricated daily amount', 'faithfulness':'All material answer claims supported by visible supplied documents and cited sources; citation membership alone is not semantic support', 'denominators':'8 answerable questions x2 repeats per arm, 2 negative controls x2 separately. Repeats are not independent questions.'},
    'stops':['First transport/HTTP/schema/identity error, no retry or model fallback', 'Budget admission exceeds $3 including embedding', 'Frozen source/code/questions/rubric drift', 'No post-result tuning, question replacement or adoption'],
    'limits':['New project evaluation reports, not guaranteed absent from model training', 'Same assistant authors rubric and reviews answers; no independent blind judge', 'Pipeline comparison includes extraction, boundaries and context metadata jointly', 'Small two-company sample is descriptive only'],
})
print('Question and source selection locked. No model or embedding calls.')
