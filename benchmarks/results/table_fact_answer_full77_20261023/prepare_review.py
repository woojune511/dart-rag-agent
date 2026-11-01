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
    for p,h in load(OUT/'freeze.json')['files'].items():assert sha(OUT/p)==h,('Original freeze',p)
    for p,h in load(OUT/'resume01/freeze.json')['files'].items():assert sha(OUT/'resume01'/p)==h,('Resume freeze',p)
    live=OUT/'combined'
    assert load(live/'execution_result.json')['status']=='COMPLETED'
    for segment,h in load(live/'origin.json')['raw_seals'].items():
        assert sha(OUT/segment/'raw_seal.json')==h
        for p,d in load(OUT/segment/'raw_seal.json')['files'].items():assert sha(OUT/segment/p)==d
    for p,h in load(live/'raw_seal.json')['files'].items():assert sha(live/p)==h,p
    rows=[json.loads(x) for x in (live/'answers.jsonl').read_text('utf-8').splitlines()]
    assert len(rows)==308 and len({r['label'] for r in rows})==308
    assert {r['label'] for r in rows}=={r['label'] for r in load(OUT/'schedule.json')}
    requests={(x['case_id'],x['arm']):x for x in load(OUT/'requests.json')}
    rubric=load(OUT/'rubric.json')
    public={c['case_id']:{k:v for k,v in c.items() if k not in ['arm_evidence','answer_scores','baseline_sol12_grade','baseline_all_axes_pass','historical_nonpass_focus']} for c in rubric['cases']}
    sizes={c['case_id']:sum(e['packet_bytes'] for e in requests.values() if e['case_id']==c['case_id']) for c in rubric['cases']}
    sets={f'batch{i:02d}':[] for i in (1,2,3)}
    weight={k:0 for k in sets}
    for cid in sorted(sizes,key=lambda x:(-sizes[x],x)):
        g=min((k for k in sets if len(sets[k])<26),key=lambda k:(weight[k],len(sets[k]),k))
        sets[g].append(cid);weight[g]+=sizes[cid]
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
        rawpath=(OUT/'live' if row['attempt']<=43 else OUT/'resume01/live')/f"{row['attempt']:03d}_response.json"
        mapping.append({'review_id':rid,'case_id':row['case_id'],'arm':row['arm'],'repetition':row['repetition'],'label':row['label'],'group':g,
                        'source_response_path':rawpath.relative_to(OUT).as_posix(),'source_response_sha256':sha(rawpath),
                        'frozen_request_sha256':requests[row['case_id'],row['arm']]['body_sha256']})
    for g,items in groups.items():
        folder=OUT/'masked_review'/g
        put(folder/'items.json',items)
        put(folder/'rubric.json',{'grades':rubric['grades'],'global_rules':rubric.get('global_rules',{}),'cases':[public[cid] for cid in sets[g]],
            'review_rule':'Grade supplied answers against their actual packet and cited sources. Arm and repetition are masked; packet representation can reveal condition. Do not inspect mapping, live outputs or other review set.'})
        put(folder/'instructions.json',{'count':len(items),'external_calls':0,'no_generation':True,
            'output':'review.json: {reviews:[{review_id,case_id,accuracy,completeness,faithfulness,appropriate_abstention,units:[{unit_id,status,note}],unsupported_claims:[],citation_validity,notes,receipts:[]}]}',
            'receipts':'Identify actual cited source_id and matching text/fact-unit/frame supporting core judgement. Preserve uncertainty as AMBIGUOUS; HOLD accuracy/completeness null with unit-level diagnosis.',
            'global_caption_rule':'Do not penalize missing copied raw-caption fields alone. Read source text/context/metadata/rows/columns together. Explicit conflicts and missing source support remain errors.',
            'unit_rule':'Preserve every frozen unit ID; alias or optional records are not independent required facts. Do not add new mandatory conditions.',
            'schema':'Scored axes: PASS/PARTIAL/FAIL/AMBIGUOUS; HOLD accuracy/completeness JSON null. appropriate_abstention: PASS/PARTIAL/FAIL/NOT_APPLICABLE/AMBIGUOUS. citation_validity: PASS or FAIL for ID membership only. Units: FULFILLED/PARTIAL/OMITTED/INCORRECT/UNRESOLVED_CRITERION with nonempty note. At least one actual evidence receipt and judgement note per review. Unsupported claims array may be empty. Never duplicate unit or review IDs.',
            'blindness_limit':'Fresh-context reviewer; condition labels hidden but source length/representation and rubric hints may reveal condition. Not independent human review.'})
    put(OUT/'review_mapping.json',mapping)
    assert len(mapping)==len({r['review_id'] for r in mapping})==308
    assert len({(r['case_id'],r['arm'],r['repetition']) for r in mapping})==308
    put(OUT/'review_preparation.json',{'status':'SEALED_THEN_MASKED','raw_seal_sha256':sha(live/'raw_seal.json'),
        'counts':{g:len(items) for g,items in groups.items()},'mapping_sha256':sha(OUT/'review_mapping.json'),
        'source_review_authority':'Same pre-generation frozen rubric; no judge model API calls.'})
    print('MASKED_REVIEW_READY', {g:len(items) for g,items in groups.items()})

if __name__=='__main__':main()
