"""Apply explicit source-reviewed adjudications; never regenerate answers or rescore by keywords."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from validate_reviews import validate

OUT = Path(__file__).resolve().parent

def load(name):
    return json.loads((OUT / name).read_text('utf-8'))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def put(name, value):
    with (OUT / name).open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)

def main():
    for name, digest in load('initial_review_seal.json')['files'].items():
        assert sha(OUT / name) == digest, name
    initial = load('initial_reviews.json')['reviews']
    reviews = copy.deepcopy(initial)
    index = {r['review_id']: r for r in reviews}
    mapping = {m['review_id']: m for m in load('review_mapping.json')}
    cases = {c['case_id']: c for c in load('rubric.json')['cases']}
    answers = {a['label']: a for a in map(json.loads, (OUT / 'combined/answers.jsonl').read_text('utf-8').splitlines())}
    cross = load('crosscase_adjudication.json')
    for name, digest in cross['provenance']['input_sha256'].items():
        assert sha(OUT / name) == digest, name
    ski = next(x for x in cross['adjudications'] if x['case_id'] == 'SKI_T1_068')
    adjustments = []
    for rid in ('R204', 'R278'):
        r = index[rid]
        before = copy.deepcopy(r)
        assert r['case_id'] == 'SKI_T1_068' and r['faithfulness'] == 'PASS'
        r['faithfulness'] = 'PARTIAL'
        r['unsupported_claims'] = [{
            'claim': '보충 설명의 SK온 자체 연결 영업손실 581,824백만원 귀속',
            'issue': '수치·기간·연결 표시·단위는 인용한1912:205에서 확인된다. SK온 주체 연결은 미인용181:1과1913:206의 3개년 매출 대응을 거쳐야 하며 직접 명시된 연결이 아니다. 이 해석은 강하게 뒷받침되지만 실제 인용 세트의 주체 지지는 불충분하다. 숫자가 틀렸다고 판정한 것이 아니다.',
            'kind': 'insufficient_entity_link_citation',
        }]
        r['notes'] = ('주결과581,816/1,903,886과30.56% 계산, 실제 백만원 표제 복구는 충족하므로 정확도·완전성 PASS 및 모든 필수 unit FULFILLED를 유지한다. '
                      '다만 보충한 SK온 자체 연결581,824의 소유자 연결에 필요한181:1/1913:206은 실제 packet에 있지만 인용하지 않았다. '
                      '3개년 매출의 강한 대응을 고려해 값 오류나 허구로 판정하지 않고, 사전 secondary-claim/inadequate-citation 규칙에 따라 전체 출처 충실도만 PARTIAL로 조정한다. '
                      '최초 PASS 판정과 후속 독립 교차 검토는 별도 파일에 보존한다.')
        r['receipts'] = copy.deepcopy(ski['receipts'])
        adjustments.append({'review_id': rid, 'case_id': r['case_id'], 'before': before, 'after': copy.deepcopy(r),
                            'changed_axes': ['faithfulness'], 'changed_units': [],
                            'authority': 'Frozen faithfulness.PARTIAL; crosscase_adjudication.json plus root source inspection. No new mandatory owner-copy rule.'})
    r = index['R144']
    before = copy.deepcopy(r)
    assert r['case_id'] == 'SKH_T1_060'
    for u in r['units']:
        if u['unit_id'] in ('long_borrowing', 'bond'):
            assert u['status'] == 'PARTIAL'
            u['status'] = 'FULFILLED'
            value = '10,121,033' if u['unit_id'] == 'long_borrowing' else '9,490,410'
            u['note'] = f'요청된 원소 {value}백만원을 비유동 구성항목으로 괄호 안에 직접 보존했다. 계산식에서 유동성 포함 합계를 선택한 오류는 별도 전체 요청 판정에 남긴다.'
    r['notes'] = ('단기 및 명명된 비유동 장기차입금·사채의 개별 값은 실제 답변에 직접 보존되어 세 unit 모두 FULFILLED이다. '
                  '그러나 요청용 계산식은 유동성 포함29,468,632를 사용해 명명된 세 항목23,757,090과 다르고, 두 자산 분모도 실제 packet에 없다. '
                  '개별 값의 보존과 잘못 선택한 요청 계산 범위를 분리하여 전체 정확도·완전성 PARTIAL, 출처 충실도 PASS를 유지한다. R203에는 두 비유동 숫자가 직접 표기되지 않아 기존 PARTIAL을 유지한다.')
    adjustments.append({'review_id': 'R144', 'case_id': r['case_id'], 'before': before, 'after': copy.deepcopy(r),
                        'changed_axes': [], 'changed_units': ['long_borrowing', 'bond'],
                        'authority': 'Frozen individual unit acceptance versus separate requested calculation completion; explicit displayed values and crosscase follow-up.'})
    warnings = validate(reviews, mapping, cases, answers)
    assert warnings == [], warnings
    confirmations = [
        {'case_id': 'HYU_T3_072', 'review_ids': ['R050','R076','R247','R303'], 'decision': 'Retain FAIL/FAIL/PASS for A and PARTIAL/PARTIAL/PASS for C. C source1246:4 row143 directly supplies25.81%,1,294,367백만원 and recent-business-year loss803,742백만원; the requested full income summary remains incomplete. Do not call this full answer recovery.'},
        {'case_id': 'POS_T1_057', 'review_ids': ['R017','R148','R158','R182'], 'decision': 'Retain partial completion and faithful abstention. Supplied finance-cost row contains1,001,290백만원; operating-income operand is absent from actual packets, not proven absent from the original report.'},
        {'case_id': 'KAB_T3_067', 'review_ids': ['R088','R175','R205','R230'], 'decision': 'Retain R230 secondary chronology PARTIAL. Source36:0 says recent coupon-service launch, not a specific2023 launch. C avoids that extra assertion; the narrative source is unchanged, so do not attribute this one-repeat difference directly to appended table facts.'},
        {'case_id': 'HYU_T2_010', 'review_ids': ['R007','R012','R177','R189'], 'decision': 'Retain HOLD and R177 faithfulness PARTIAL: the difference between calculated11.4% and stated11.5% is visible but a rounding cause is not given. A/C requests are byte-identical; this observed difference is generation variation, not an effect of the table append.'},
        {'case_id': 'SAM_T2_027', 'review_ids': ['R034','R065','R151','R267'], 'decision': 'Retain HOLD and C faithfulness AMBIGUOUS, not forced FAIL. Source674:1 describes2023 product expansion and a company-wide2024 intention; A explicitly limits future-DS interpretation whereas C states direction with narrower limitations. Exact future-DS mapping remains unresolved. Appended facts did not add a new strategy paragraph.'},
        {'case_id': 'MIX_T4_062', 'review_ids': ['R130','R141','R171','R224'], 'decision': 'Retain frozen refusal-policy FAIL for all4 outputs. Hypothetical100/259*100 is correctly labelled and arithmetically valid; separate faithfulness-axis interpretation remains AMBIGUOUS. Do not falsely describe this as an invented actual100조 expense or arithmetic failure.'},
        {'case_id': 'MIX_T3_063', 'review_ids': ['R028','R265','R275','R282'], 'decision': 'Retain HOLD. C recovers the two largest individual-company carrying amounts under the stated interpretation, but missing profit table and frozen ranking-population ambiguity remain. No main complete-success credit.'},
        {'case_id': 'POS_T1_075', 'review_ids': ['R078','R146','R291','R308'], 'decision': 'Retain HOLD and PARTIAL claim support in both arms.43,248백만원/2023/consolidated appears in1241:79 but the operating owner is unbound; another EBITDA table is not an interchangeable company total.'},
        {'case_id': 'CEL_T3_015 and SAM_T3_003', 'decision': 'Two additional byte-identical input controls retain PASS on all scored axes in all repetitions. HYU_T2_010 is the third identical-input control and is HOLD, not common-answerable.'},
    ]
    log = {'at': datetime.now(timezone.utc).isoformat(), 'status': 'ROOT_ADJUDICATED_WITH_INITIALS_PRESERVED',
           'rubric_sha256': sha(OUT/'rubric.json'), 'initial_seal_sha256': sha(OUT/'initial_review_seal.json'),
           'crosscase_sha256': sha(OUT/'crosscase_adjudication.json'), 'criteria_changed': False,
           'adjusted_answers': 3, 'faithfulness_adjustments': 2, 'unit_state_adjustments': 2,
           'adjustments': adjustments, 'unchanged_boundary_confirmations': confirmations,
           'review_scope': 'Three masked native reviewers read all308 answers. Root reviewed changed/sentinel/control cases and exact source boundaries; a crosscase follow-up reviewed SKI and SKH without peer judgments. Not independent human or cross-family validation.',
           'validation_warnings': warnings}
    put('adjudication_log.json', log)
    put('adjudicated_reviews.json', {'reviews': reviews, 'status': 'SOURCE_REVIEW_ADJUDICATED',
                                     'initial_reviews_sha256': sha(OUT/'initial_reviews.json'),
                                     'adjudication_log_sha256': sha(OUT/'adjudication_log.json')})
    print('ADJUDICATED308;3 answers adjusted;2 faithfulness axes and2 individual unit states;0 warnings;frozen criteria unchanged')

if __name__ == '__main__':
    main()
