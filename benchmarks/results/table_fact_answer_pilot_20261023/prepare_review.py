"""Prepare arm-masked source review only after every raw response is sealed."""
import hashlib
import json
from pathlib import Path
import random

OUT=Path(__file__).resolve().parent
def load(p): return json.loads(Path(p).read_text('utf-8'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,x):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2)

def main():
    live=OUT/'live'
    assert load(live/'execution_result.json')['status']=='COMPLETED'
    for p,h in load(live/'raw_seal.json')['files'].items():assert sha(live/p)==h,p
    rows=[json.loads(x) for x in (live/'answers.jsonl').read_text('utf-8').splitlines()]
    assert len(rows)==72
    requests={(x['case_id'],x['arm']):x for x in load(OUT/'requests.json')}
    rubric=load(OUT/'rubric.json')
    public={c['case_id']:{k:v for k,v in c.items() if k not in ['arm_evidence','answer_scores']} for c in rubric['cases']}
    sets={'numeric':['HYU_T3_072','SKI_T1_068','SAM_T1_001','POS_T1_057','SKH_T1_060','SAM_T4_029'],
          'narrative':['MIX_T3_063','KAK_T3_055','MIX_T2_047','MIX_T3_048','CEL_T3_040','HYU_T4_079']}
    random.Random(2026102301).shuffle(rows)
    mapping=[];groups={g:[] for g in sets}
    for i,row in enumerate(rows,1):
        rid=f'R{i:03d}'
        g=next(g for g,ids in sets.items() if row['case_id'] in ids)
        folder=OUT/'masked_review'/g
        (folder/'packets').mkdir(parents=True,exist_ok=True)
        packet=json.loads(requests[row['case_id'],row['arm']]['body']['input'][1]['content'])
        put(folder/'packets'/f'{rid}.json',packet)
        groups[g].append({'review_id':rid,'case_id':row['case_id'],'question':packet['query'],
            'answer':row['answer'],'raw_text':row['raw_text'],'structural_error':row['structural_error'],
            'unknown_citations':row['unknown_citations'],'packet_path':f'packets/{rid}.json'})
        mapping.append({'review_id':rid,'case_id':row['case_id'],'arm':row['arm'],'repetition':row['repetition'],'label':row['label'],'group':g})
    for g,items in groups.items():
        folder=OUT/'masked_review'/g
        put(folder/'items.json',items)
        put(folder/'rubric.json',{'grades':rubric['grades'],'cases':[public[cid] for cid in sets[g]],
            'review_rule':'Grade supplied answers against their actual packet and cited sources. Arm and repetition are masked; packet representation can reveal condition. Do not inspect mapping, live outputs or other review set.'})
        put(folder/'instructions.json',{'count':len(items),'external_calls':0,'no_generation':True,
            'output':'review.json: {reviews:[{review_id,case_id,accuracy,completeness,faithfulness,appropriate_abstention,units:[{unit_id,status,note}],unsupported_claims:[],citation_validity,notes,receipts:[]}]}',
            'receipts':'Identify actual cited source_id and matching text/fact-unit/frame supporting core judgement. Preserve uncertainty as AMBIGUOUS; HOLD accuracy/completeness null with unit-level diagnosis.',
            'blindness_limit':'Fresh-context reviewer; condition labels hidden but source length/representation and rubric hints may reveal condition. Not independent human review.'})
    put(OUT/'review_mapping.json',mapping)
    put(OUT/'review_preparation.json',{'status':'SEALED_THEN_MASKED','raw_seal_sha256':sha(live/'raw_seal.json'),
        'counts':{g:len(items) for g,items in groups.items()},'mapping_sha256':sha(OUT/'review_mapping.json'),
        'source_review_authority':'Same pre-generation frozen rubric; no judge model API calls.'})
    print('MASKED_REVIEW_READY', {g:len(items) for g,items in groups.items()})

if __name__=='__main__':main()
