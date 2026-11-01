"""Explicit root adjudication; retain original masked reviews unchanged."""
import copy
import hashlib
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent
def load(p):return json.loads(Path(p).read_text('utf-8'))
def enc(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,v):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,indent=2)

mapping={r['review_id']:r for r in load(OUT/'review_mapping.json')}
reviews=[]
for g in ['numeric','narrative']:
    reviews.extend(copy.deepcopy(load(OUT/f'masked_review/{g}/review.json')['reviews']))
requests={(r['case_id'],r['arm']):r for r in load(OUT/'requests.json')}
decisions=[]
targets={'POS_T1_057':('692:331',['1,001,290']),
         'SKH_T1_060':('277:148',['4,145,647','10,121,033','9,490,410']),
         'SAM_T1_001':('123:2',['258,935,494','6,566,976'])}
for r in reviews:
    m=mapping[r['review_id']]
    if m['arm']=='A' and r['case_id'] in targets:
        assert r['faithfulness']=='PARTIAL'
        assert all(u['status']=='AMBIGUOUS' for u in r['unsupported_claims'])
        suffix,values=targets[r['case_id']]
        packet=json.loads(requests[r['case_id'],'A']['body']['input'][1]['content'])
        d=next(d for d in packet['documents'] if d['chunk_id'].endswith(suffix))
        assert all(v in d['text'] for v in values)
        prior=copy.deepcopy(r['unsupported_claims'])
        reason=('No frozen blanket requirement that a literal caption be copied into table_fact_units. '
                'Actual transmitted value rows, columns, scope/year/unit text-context and the source-backed unique mapping support these claims. '
                'No conflicting axis or fabricated value was identified. A missing duplicated raw-caption field is a provenance-format limitation, '
                'not a new answer-faithfulness failure. Preserve task omissions and all other grades. '
                'The explicit SKI currency_binding/% conflict rule remains unchanged.')
        receipt={'source_id':d['source_id'],'chunk_id':d['chunk_id'],'document_sha256':hashlib.sha256(enc(d)).hexdigest(),
            'context':d['context'],'matching_value_lines':[line for line in d['text'].splitlines() if '|' in line and any(v in line for v in values)],
            'existing_hint_lines':[line for line in d['text'].splitlines() if any(line.startswith('['+x+':') for x in ['consolidation_scope','period_focus','unit_hint','local_heading','table_context'])]}
        r['faithfulness']='PASS'
        r['unsupported_claims']=[]
        r['evidence_format_limitations']=prior
        r['root_adjudication']={'reason':reason,'criterion_author_note':'rubric_interpretation_note.json','receipt':receipt}
        decisions.append({'review_id':r['review_id'],'label':m['label'],'field':'faithfulness','before':'PARTIAL','after':'PASS',
            'reason':reason,'receipt':receipt,'original_flags_preserved_as':'evidence_format_limitations'})
assert len(decisions)==6
assert len(reviews)==72 and len({r['review_id'] for r in reviews})==72
put(OUT/'adjudicated_reviews.json',{'reviews':reviews,'root_decisions':decisions,
    'method':'Root read all72 answers and checked changed/core source claims. First reviews were fresh-context and arm-masked; root knows arms. No scores or criterion files silently overwritten.',
    'grading_boundary':'Caption-only duplicate-field penalty removed in6 original-arm answers to apply pre-generation criteria consistently; no change to factual requirements, HOLD, generation or saved inputs.',
    'masked_review_sha256':{g:sha(OUT/f'masked_review/{g}/review.json') for g in ['numeric','narrative']},
    'rule_interpretation_sha256':sha(OUT/'rubric_interpretation_note.json'),
    'generations_after_grading':0})
print('ADJUDICATED72;6 caption-only penalties corrected; original reviews preserved')
