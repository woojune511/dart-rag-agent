"""Assemble the author's bounded semantic review from immutable saved packets.

The case notes below are evaluation observations, never selection/projection rules.
No runner/projector import, source projection, retrieval, store or model execution.
"""
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('axis_evidence_check', HERE / 'axis_evidence_check.py')
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)
data = check.audit()
results = {x['case_id']: x for x in check.load(HERE / 'results.json')}
prior = check.load(check.OLD / 'postrun_axis_review.json')
contract = check.load(HERE / 'evaluation_contract.json')
watch = {x['case_id']: x for x in contract['cases'] if x.get('audit_binding_watch')}
assert set(watch) == {x['case_id'] for x in prior['case_axis_reviews']}

notes = {
 'KBF_T2_018': {
  'observation': '66개625:2 및48개1846:5 핵심 단위는 동일하다. 1842:1의 나머지 경영비율14개와1126:483 특수관계자 손익328개가 추가됐다.',
  'boundaries': '1842:1은 십억원/%/%p 혼합 단위와2023금액/비율·전년대비·2022·2021 열을 유지한다. 1126:483은 관계기업/공동기업의 회사명·계정명과당기/전기·백만원·연결주석을 유지하므로 그룹전체 충당금 전입액으로 합치지 않는다. 상대 당기의 절대연도 정규화와 그룹총액/관계자거래액의 의미 선택은 자동 확정되지 않았다.'},
 'SKH_T3_080': {
  'observation': '패킷 전체가 양 arm에서 동일하다. 연결381:252와별도633:233의 손실/이익/현금흐름 조정과당기·백만원 표시는 그대로다.',
  'boundaries': '현금흐름 조정의 부호를 손익 부호로 바꾸는 해석, 질문에서 생략된 연결/별도 범위, 상대 당기의 절대연도는 새로 검증하지 않았다.'},
 'NAV_T3_007': {
  'observation': '패킷 전체가 동일하며353:229의63개 단위도 그대로다. 영업권 열의 손상및환입(19,630,042)와기말2,578,089,956,당기·천원·연결 문맥이 유지된다.',
  'boundaries': '이미 존재한 값을 새로운 개선으로 세지 않는다. 모델 답변이나 부호 해석을 재평가하지 않았다.'},
 'MIX_T3_048': {
  'observation': '연결127:6의117개 단위는 동일하다. 별도383:4의90개 단위가 추가되어 배당금의지급 제55기(9,810,119)와기존 연결(9,864,474)가 함께 명시적으로 보인다.',
  'boundaries': '새 표는 원래문서context의separate와4.재무제표/현금흐름표 문맥,제55기2023.01.01~12.31·백만원 캡션을 유지한다. 서로 다른 연결/별도 금액을 같은 값으로 합치지 않았지만 대안 금액 노출이 늘었다. 현금배당/결정배당/환원정책의 의미 구분과 모델 선택 성공은 미측정이다.'},
 'HYU_T2_010': {
  'observation': '양 arm 모두 추가 단위0이며 원래 A12와 동일하다. 한 셀 세금서술798:217/438:296/1212:4는 계속no_valid_numeric_units이다.',
  'boundaries': '미국판매 및정책 원문은 보존되지만 주체모호성과11.4/11.5 차이, 별도/연결 해석의 HOLD는 그대로다. 예산 확대가 text-only 관계를 복구하지 않는다.'},
 'POS_T1_057': {
  'observation': '패킷 전체가 동일하다. 692:331의연결당기 이자비용1,001,290백만원과23개 단위가 보존된다.',
  'boundaries': '분자 영업이익을 새로 찾거나 계산하지 않았다. 원/백만원 표시 차이와 비율의 의미 완결성을 이번 축 검토에서 해결했다고 세지 않는다.'},
 'SKH_T1_060': {
  'observation': '180개 단위가 추가됐다. 연결당기사채281:152는15→67개이고,별도당기차입금531:1318개,연결전기사채282:15337개,별도당기사채535:13567개,연결전기차입금278:1498개,별도전기차입금532:1328개가 추가됐다.',
  'boundaries': '연결/별도는 다른 source_id와주석경로로,당기/전기는 각표 preceding caption으로 유지된다. 연결당기차입금합계29,468,632와별도당기25,425,313백만원을 합치지 않는다. 이자율(%)행의0.0211등 원문과화폐액행이 같은표에 있으나 백만원을 모든 행의 단위로 자동 확정하지 않는다. 상대당기/전기,유동/비유동합계의 선택 및유무형자산분모 부재는 그대로다.'},
 'SAM_T3_028': {
  'observation': '패킷 전체가 동일하다.319:19128개 단위와재고자산평가손실(환입) 등5,037,579의등 한정어가 보존된다.',
  'boundaries': '기간 중현금흐름조정과기말충당금잔액을 같다고 선언하지 않는다. 기존PASS보존과새답변성공은 다르다.'},
 'HYU_T3_072': {
  'observation': '1246:4의단위432→1,701개. Motional expanded row143의12개가모두 실제160KiB패킷에추가된다.기초지분율25.92와기말25.81,기초/기말장부1,294,367,최초취득금액1,267,859를다른열에유지한다.',
  'boundaries': '2020.03.01은row-axis의literal날짜이고column-prefix에최초취득일자가함께있다.2023년12월31일기준일과구분되며period_text=2020을새확정기간으로복사하지않았다.백만원·주·%혼합단위는literalcaption으로남아있고정규화scalar가아니다.최근사업연도재무현황의총자산3,150,225/당기순손익-803,742를2023연결요약손익4항목이나연결26%/700,691과한묶음으로합치지않는다.실제원문의해당별도투자범위를명시해야하며fullprofit요구는별도판정이다.'},
 'LGE_T2_052': {
  'observation': '패킷 전체가동일하다.제품21:2가격1.89/1.62/1.28의3개단위와USD캡션은유지되며원재료24:2는여전히numericunit0이다.',
  'boundaries': '원재료33.47/kg/43.99/kg와별도USDcaption청크23:1은A12에그대로있다.직접물리연결의T12보강손실은이budget변경으로복구되지않았다.제4기↔2023의정규화는미검증이다.'},
 'POS_T1_075': {
  'observation': '패킷전체가동일하고1241:79/1283:121/1285:123의15/12/21개단위도동일하다.',
  'boundaries': '기간·백만원·EBITDA값은남아있지만저장boundcontext에운영회사heading이없다.파일회사POSCO홀딩스를표의포스코스틸리온/포스코인터내셔널주체로자동확정하지않는다.원문다른위치에서알려진주체를이번패킷이새로전달했다고세지않으며HOLD유지.'},
 'SKI_T1_068': {
  'observation': '1713:6의144개단위와백만원caption은완전히동일하다.182개추가분은304:4나머지72개,1915:208/1916:209/1914:207각24개,181:1 18개,1738:31 20개이다.',
  'boundaries': '배터리사업영업손익(581,816)과-31%,총계1,903,886과100%는금액/비율열을유지한다.기존A12 [unit_hint: %]와실제백만원caption충돌은여전히존재하지만새scalarunit으로복사하지않았다.새자회사표의SK Battery America/SK Battery Manufacturing/SK On Hungary주체는각각같은표의preceding literal로남는다.1738:31 frame에는SK에너지명이없지만원래text의SK에너지㈜와그종속회사문장이남아있으므로이를읽어야한다.배터리세그먼트와SK온법인/자회사실적을자동합치지않는다.'},
 'SKI_T2_069': {
  'observation': '패킷전체가동일하다.1738:31의영업이익409,219/2,600,786,2023/2022,-84.3%,백만원·%caption및20개단위가보존된다.',
  'boundaries': 'SK에너지㈜와그종속회사주체는원래본문에있으며frame만으로완결됐다고세지않는다.파일회사정보로대체하지않는다.'},
 'MIX_T3_063': {
  'observation': '360개단위가새로전달된다.396:272전기장부금액121개와384:260당기지분율/장부금액239개를각표의회사열·연결주석·당기/전기·천원caption과함께보존한다.당기A Holdings15,338,412,557및Mirae Asset-Naver341,924,825가실제패킷에보인다.',
  'boundaries': '같은A Holdings의전기15,825,770,829와당기금액은다른tablelocator/caption이다.지분율50.00%를천원으로전파하지않는다.합계열/순위모집단HOLD는그대로이고당기순손익표426:302는이추가분에없으므로장부금액에서손익을추정하지않는다.'},
 'NAV_T2_006': {
  'observation': '패킷전체가동일하다.1559:7의24개단위에금액/퍼센트literal과십억원caption이그대로이고1060:936의Poshmark한셀서술은여전히numericunit0이다.',
  'boundaries': '원래본문의취득후기여473,849/19,063백만원과기초부터연결했다면의가정9,676,687/815,379백만원은보존된다.실제/가정관계나순손실/영업손실을새로등치하지않는다.잘못된저장percentage-unit_hint는새payload에내보내지않았다.'},
 'CEL_T2_014': {
  'observation': '패킷전체가동일하다.103:44/108:49의파이프라인·단계·기준일이후신청표는계속numericunit0이다.',
  'boundaries': '원래연구시작연도/현황/2024신청/기준일이후문장은보존된다.연구시작을승인연도로,신청을승인으로바꾸지않는다.큰예산이text-only스키마의보강누락을해결하지않는다.'},
 'CEL_T3_040': {
  'observation': '패킷전체가동일하다.연결517:35749개와별도917:32048개단위의손실·환입·폐기,당기·천원·범위가그대로다.',
  'boundaries': '질문이생략한연결범위,상대당기연도,gross와net해석은자동확정하지않으며새답변성공으로세지않는다.'},
 'HYU_T2_035': {
  'observation': '패킷전체가동일하다.22:8 numericunit0/21:7중복첫소유자처리가유지된다.원래A12미국HMMA–2023GV70EV/인도HMI–2023아이오닉5행은그대로다.',
  'boundaries': '과거country표의잘못추정된3행prefix가새160unit으로추가된것은아니다.구조보강부재와원래관계근거보존을구분한다.E-GMP/차종별판매연결은여전히HOLD이다.'},
 'MIX_T1_064': {
  'observation': '패킷전체가동일하다.1047:3 24개/408:26615개단위의매출·원가·판관비축을유지한다.',
  'boundaries': '1047:3 frame의단위caption부재는그대로이나원래text백만원은남아있다.단일frame만으로완결됐다고세지않으며차량부문과개별브랜드수익성을같다고선언하지않는다.'},
}


def bundle(cid, uid, arm='160KiB'):
    packet = check.load(HERE / f'packets/{cid}_{arm}.json')
    return next(d for d in packet['documents'] if d['chunk_id'] == uid)


def evidence_units(cid, uid, rows=None, predicate=None, arm='160KiB'):
    b = bundle(cid, uid, arm)['table_fact_units']
    units = [check.unpack(b, u) for u in b['units']]
    return [u for u in units if (rows is None or u['at'][0] in rows)
            and (predicate is None or predicate(u))]


def table_summary(cid, uid):
    result = results[cid]
    decisions = {label: next(x for x in result['arms'][label]['decisions'] if x['uid'] == uid)
                 for label in ('64KiB', '160KiB')}
    out = {'uid': uid, 'status64': decisions['64KiB']['status'], 'status160': decisions['160KiB']['status'],
           'units64': decisions['64KiB'].get('unit_count', 0), 'units160': decisions['160KiB'].get('unit_count', 0)}
    doc = bundle(cid, uid)
    out['original_context'] = doc['context']
    out['legacy_scalar_prefixes_preserved'] = [line for line in doc['text'].splitlines()
        if line.startswith(('[unit_hint:', '[period_focus:', '[consolidation_scope:'))]
    if 'table_fact_units' in doc:
        b = doc['table_fact_units']
        out['frame'] = check.frame(b)
        out['representative_first_and_last_units'] = [check.unpack(b, b['units'][0]), check.unpack(b, b['units'][-1])]
    return out


checks = data['checks']
case_reviews = []
for previous in prior['case_axis_reviews']:
    cid = previous['case_id']
    result = results[cid]
    checkrow = next(x for x in checks if x['case_id'] == cid)
    targets = {x['uid'] for x in previous['target_witness_review']}
    changed = {x['uid'] for x in data['reviewed_tables'].get(cid, []) if x['added_units']}
    case_reviews.append({
        'case_id': cid, 'baseline_disposition_retained': watch[cid]['evaluation_disposition'],
        'prior_review_role': 'Author review with shared case history; not blind or independent projector review.',
        'axis_review_disposition': 'PRESERVED_WITH_ADDED_LITERAL_EVIDENCE' if checkrow['added_unit_count'] else 'EXACT_PACKET_UNCHANGED',
        'packet64_equals_packet160': check.load(HERE / f'packets/{cid}_64KiB.json') == check.load(HERE / f'packets/{cid}_160KiB.json'),
        'checks': checkrow,
        'packet_bytes': {a: result['arms'][a]['packet_bytes'] for a in ('64KiB', '160KiB')},
        'attached_units': {a: result['arms'][a]['attached_units'] for a in ('64KiB', '160KiB')},
        'observations': notes[cid],
        'inspected_table_axis_examples': [table_summary(cid, uid) for uid in sorted(targets | changed)],
        'answer_regrade': 'NOT_PERFORMED_NO_GENERATION',
        'confirmed_new_wrong_semantic_assertions_in_inspected_axes': 0,
        'semantic_completeness_certified': False,
    })

motional = evidence_units('HYU_T3_072', '20240313001451:1246:4', rows={143})
assert len(motional) == 12
assert all('최초취득일자' in [x[-1] for x in u['column_axes']] for u in motional)
assert all([x[-1] for x in u['row_axes']] == ['Motional', '비상장', '2020.03.01', '경영참여'] for u in motional)

mix_uid = '20240313001451:1149:18'
mix_bundles = {arm: bundle('MIX_T2_047', mix_uid, arm)['table_fact_units'] for arm in ('64KiB', '160KiB')}
mix_examples = {arm: check.unpack(b, b['units'][0]) for arm, b in mix_bundles.items()}
mix_counts = {arm: sum(any(b['cells'][i][-1] == '김걸' for i in u[4]) for u in b['units'])
              for arm, b in mix_bundles.items()}
mix_new_example = next(u for t in data['reviewed_tables']['MIX_T2_047'] if t['uid'] == mix_uid
                       for u in t['added_units'] if u['at'] == [45, 8])

remaining = []
for cid, result in results.items():
    if not result['arms']['160KiB']['budget_rejected_units']:
        continue
    tables = []
    for d in result['arms']['160KiB']['decisions']:
        rejected = [u for u in d.get('units', []) if u['status'] == 'rejected_byte_budget']
        if rejected:
            attached = [u for u in d.get('units', []) if u['status'] == 'attached']
            tables.append({'uid': d['uid'], 'attached': len(attached), 'rejected': len(rejected),
                           'first_rejected_at': rejected[0]['at'], 'last_rejected_at': rejected[-1]['at'],
                           'last_attached_at': attached[-1]['at'] if attached else None})
    remaining.append({'case_id': cid, 'packet_bytes': result['arms']['160KiB']['packet_bytes'],
                      'remaining_budget_rejected_units': result['arms']['160KiB']['budget_rejected_units'],
                      'tables': tables,
                      'original_A12_preserved': next(x for x in checks if x['case_id'] == cid)['original_A12_preserved_both'],
                      'interpretation': 'Fixed physical order and atomic dependency cost leave these saved units untransmitted. No replacement or newly omitted original source; no answer failure inferred.'})

report = {
 'schema_version': 'saved_fact_budget77_axis_review_v1',
 'status': 'ANALYZED_SAVED_OUTPUTS',
 'date': '2026-10-23',
 'reviewer_role': 'Prior FCT projector author; shared earlier case context; not blind and not an independent source-verification review.',
 'scope': {'watch_cases': 19, 'full77_lost_unit_and_frame_checks': True,
           'manual_semantic_coverage': '19 fixed axis-watch cases plus the two remaining budget-rejection cases. All changed watch table frames and representative role-bearing units inspected; this is not exhaustive semantic regrading of every one of the 8,307 added units.',
           'source_boundary': 'Read frozen packets/decisions and earlier author review only. No XML reparse or physical provenance rerun here; no peer numeric/boundary verdicts consumed.',
           'model_API_calls': 0, 'source_projection_recomputations': 0, 'retrieval_runs': 0, 'new_answers': 0, 'store_opened': False},
 'frozen_criteria': {'contract_watch_count': len(watch), 'contract_watch_ids_exactly_match_prior_review': True,
                     'HOLD_or_baseline_grades_changed': False, 'required_facts_regraded_by_this_review': False},
 'full77_saved_packet_checks': checks,
 'summary': {
    'A12_preserved_exactly_both_caps': sum(x['original_A12_preserved_both'] for x in checks),
    'saved64_exactly_reproduced': sum(x['saved_64_packet_exact'] for x in checks),
    'retained_units_with_same_wire_value_row_column_axes': sum(x['retained_unit_count'] for x in checks),
    'added_units': sum(x['added_unit_count'] for x in checks),
    'lost_units': sum(len(x['lost_units']) for x in checks),
    'changed_retained_unit_payloads': sum(len(x['changed_retained_units']) for x in checks),
    'lost_table_frames': sum(len(x['lost_table_frames']) for x in checks),
    'changed_shared_table_frames': sum(len(x['changed_shared_frames']) for x in checks),
    'added_table_frame_events': sum(len(x['added_table_frames']) for x in checks),
    'watch_cases_reviewed': len(case_reviews),
    'watch_cases_with_added_units': sum(x['checks']['added_unit_count'] > 0 for x in case_reviews),
    'watch_exactly_unchanged_packets': sum(x['packet64_equals_packet160'] for x in case_reviews),
    'confirmed_new_wrong_semantic_axis_assertions_in_inspected_claims': 0,
    'semantic_safety_certified': False,
    'physical_source_verification_count_by_this_reviewer': None,
 },
 'case_axis_reviews': case_reviews,
 'Motional_role_and_delivery_evidence': {
    'uid': '20240313001451:1246:4', 'source_table_locator': bundle('HYU_T3_072', '20240313001451:1246:4')['table_fact_units']['table_locator'],
    'Motional_expanded_row': 143, 'Motional_units64': 0, 'Motional_units160': len(motional),
    'actual_delivered_units': motional,
    'frame_contexts': bundle('HYU_T3_072', '20240313001451:1246:4')['table_fact_units']['literal_source_contexts'],
    'observed_role_separation': '2020.03.01 is under the literal 최초취득일자 column. 기초잔액/기말잔액/최근사업연도재무현황 are separate column groups. 2023-12-31 is the separately preserved source caption date.',
    'semantic_limits': 'The partial separate-investment alternative must not be combined with consolidated26%/700,691. 최근사업연도 does not itself certify each financial measure as the requested2023 consolidated profit summary. Saved source validity and these12 delivered units do not supply the absent named four-item profit table.'},
 'SKI_legacy_conflict_preserved': {
    'uid': '20240320000950:1713:6',
    'legacy_scalar': '[unit_hint: %]',
    'literal_monetary_caption': '(단위 : 백만원)',
    'caption_and_all144units_equal_across_caps': True,
    'inspected_value_rate_rows': evidence_units('SKI_T1_068', '20240320000950:1713:6', rows={12, 24}),
    'interpretation': 'Existing scalar/source-caption conflict persists. The new arm neither deletes it nor promotes it into a new scalar semantic assignment.'},
 'MIX047_existing_inferred_prefix_exposure': {
    'uid': mix_uid, 'table_locator': mix_bundles['160KiB']['table_locator'],
    'declared_header_source_tr_indices': {a: b['declared_header_source_tr_indices'] for a, b in mix_bundles.items()},
    'unit_count64': len(mix_bundles['64KiB']['units']), 'unit_count160': len(mix_bundles['160KiB']['units']),
    'added_units': 459, 'unit_prefix_references_to_first_data_row_name': mix_counts,
    'existing_first_unit_in_each_arm': mix_examples, 'first_added_example': mix_new_example,
    'first_data_row_name_physical_origin': [2, 0, 1, 1, '김걸'],
    'literal_contexts': mix_bundles['160KiB']['literal_source_contexts'],
    'confirmed_observation': 'Stored leading-prefix cells include raw source TR2 first-person data (김걸 etc), although actual declared THEAD/TH rows are empty. The same prefix is present in all34 old units and all493 new-arm units;459 additional units repeat this pre-existing label-role ambiguity.',
    'adjudication': 'Existing inferred literal-prefix exposure expanded; not a newly created physical source mislink and not an observed model answer error. Frame/schema explicitly state prefix cells are not automatically semantic headers. This caveat prevents claiming semantic certification, but cannot establish that a future model will ignore the misleading prefix.',
    'other_context_ambiguity': 'An intermediate (1)등기임원 heading and a preceding paragraph containing (2)미등기임원 coexist. Their literals andlocators are unchanged; no entity class is automatically assigned.'},
 'remaining160_budget_rejections': remaining,
 'unresolved_semantic_boundaries': [
    'No scalar unit/period/entity normalization or automatic cross-table joins were added. Correct physical coordinates are not semantic certification.',
    'Company metadata describes the filing entity and need not identify the operating company of each table; POS075 remains unresolved, SKI1738 relies on preserved source prose.',
    'Mixed currency/percent/quantity and rate rows retain literal labels. A table-level monetary caption is not assigned to every numeric cell.',
    'Relative 당기/전기, 최근사업연도, acquisition date, stock/flow, and consolidated/separate roles remain meaning judgments; named alternatives are not merged.',
    'T12 text-only relations previously absent from FCT12 remain absent at both caps: HYU035 country/model/year, CEL014 pipeline, NAV006 acquisition narrative, LGE052 direct raw-material-table/USD binding.',
    'Higher cap exposed additional alternative scopes and irrelevant executive rows. No generation was performed, so distraction, answer correctness, omission, faithfulness and refusal regressions were not measured.',
 ],
 'interpretation': 'Within this cap-only saved-payload comparison, original A12 and every64KiB unit/frame survive unchanged. Literal delivery expands, including Motional row143. Zero newly confirmed wrong semantic link in the examined claims is a bounded author finding, not proof that all added evidence is semantically complete or harmless.',
 'artifact_sha256': {**data['input_sha256'],
    'evaluation_contract.json': check.sha(HERE / 'evaluation_contract.json'),
    'evaluation_supplement.json': check.sha(HERE / 'evaluation_supplement.json'),
    'axis_evidence_check.py': check.sha(HERE / 'axis_evidence_check.py'),
    'write_axis_review.py': check.sha(__file__),
    'prior_postrun_axis_review.json': check.sha(check.OLD / 'postrun_axis_review.json')},
}
(HERE / 'postrun_axis_review.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'path': str(HERE / 'postrun_axis_review.json'), 'sha256': check.sha(HERE / 'postrun_axis_review.json'), 'summary': report['summary']}, ensure_ascii=False))
