"""Sealed outputs to masked review; no external judge or new generations."""
from common import *
import random

def main():
    need(load(OUT/'execution_result.json')['status']=='COMPLETED','All72 answers must finish before review')
    for p,h in load(OUT/'raw_output_seal.json')['files'].items():need(sha(OUT/p)==h,'Raw seal mismatch')
    outputs=[json.loads(x) for x in (OUT/'live/answers.jsonl').read_text('utf8').splitlines()]
    need(len(outputs)==72 and len({(r['case_id'],r['arm'],r['repeat']) for r in outputs})==72,'Answer coverage')
    rubric=load(PREP/'rubric18.json');cases={r['case_id']:r for r in rubric['cases']}
    instructions={
        'task':'Read every assigned answer and its ACTUAL cited model-visible packet against the frozen rubric. No previous evaluations, mappings or peer judgments.',
        'masking':'Arm/repetition are hidden; packet representation may reveal treatment. Native same-family review, not independent-human or fully blinded.',
        'accuracy':'PASS: all requested required results/relations correct, no material false extra claim. PARTIAL: incomplete but partly correct/limited abstention. FAIL: material incorrect result/relation or no correct substantive answer. Optional omissions alone do not fail.',
        'completeness':'PASS only if all frozen required facts fulfilled; PARTIAL if some; FAIL if none. Use existing fact IDs, never add mandatory criteria.',
        'faithfulness':'PASS if all material claims are supported by actual cited visible text/context/table units. PARTIAL for a limited unsupported noncentral extra claim. FAIL for unsupported/mislinked core values/entities/periods/units or invented central relations. Correct gold values or valid source IDs alone are insufficient.',
        'scope_rule':'Use the actual supplied source text and context jointly. Do not introduce a new requirement to copy a particular raw-caption field or calendar declaration if equivalent source context already supports the claim. Do not infer unsupported entity/period/scope relations from metadata alone. Mark genuine ambiguity and its exact conflicting/missing evidence explicitly.',
        'refusal':'For frozen refusal cases require abstained=true, scoped insufficiency and missing operand/relation, no invented requested result, and any explicitly requested nearest disclosed metric. No whole-report absence claim from packet absence.',
        'facts':'For each frozen required_facts id return FULFILLED/PARTIAL/OMITTED/INCORRECT/UNRESOLVED and note. These measure fulfillment; citation grounding is evaluated separately. Preserve ambiguous rubric cases, never rewrite the gold.',
        'evidence':'Inspect each cited source for every required and material added claim. Quote exact visible support and source_id; for table units give cell or expanded row,column locator. units=[row,column,value_index,row_axis_indices,column_axis_indices] references local cells. Physical linkage alone is not semantic correctness. Verify arithmetic at requested precision with Decimal.',
        'invalid_output':'If structural_errors nonempty, retain as failed with accuracy/completeness/faithfulness FAIL; no regeneration.',
        'output_schema':'{reviews:[{review_id,case_id,accuracy,completeness,faithfulness,appropriate_abstention,required_facts:[{id,status,note}],unsupported_claims:[],receipts:[{source_id,locator,quote,note}],notes}],review_limitations:[]}. Axes PASS/PARTIAL/FAIL/AMBIGUOUS; abstention NOT_APPLICABLE for answerable cases.',
        'permissions':'Read only your assigned masked_review/batch folder and listed raw source XML if needed. Write only batch/review.json. No network/model/store/env/git changes, no prior experiment outputs or other review groups.'}
    random.Random(202610248).shuffle(outputs)
    groups={f'batch{i}':[] for i in (1,2,3)};mapping=[]
    for i,a in enumerate(outputs,1):
        rid=f'R{i:03d}';group=f'batch{(int(a["case_id"][1:])-1)//6+1}';folder=OUT/'masked_review'/group
        packet=load(PREP/f'packets/{a["case_id"]}_{a["arm"]}.json')
        put(folder/'packets'/f'{rid}.json',packet)
        groups[group].append({'review_id':rid,'case_id':a['case_id'],'answer':a['answer'],'raw_text':a['raw_text'],
                             'structural_errors':a['structural_errors'],'packet_path':f'packets/{rid}.json'})
        mapping.append({'review_id':rid,'case_id':a['case_id'],'arm':a['arm'],'repeat':a['repeat'],'group':group,
                        'attempt':a['attempt'],'response_sha256':sha(OUT/'live'/f'{a["attempt"]:03d}_response.json'),
                        'packet_sha256':sha(folder/'packets'/f'{rid}.json')})
    for group,items in groups.items():
        folder=OUT/'masked_review'/group;ids=sorted({i['case_id'] for i in items})
        put(folder/'items.json',items)
        put(folder/'instructions.json',instructions)
        put(folder/'rubric.json',{'common_grading':rubric['common_grading'],'cases':[cases[cid] for cid in ids],
                                 'raw_source_paths':{cases[cid]['receipt']:str(OUT.parent/'table_fact_holdout18_preparation_20261023/sources'/cases[cid]['receipt']/'original.xml') for cid in ids}})
    put(OUT/'review_mapping.json',mapping)
    put(OUT/'review_preparation.json',{'status':'SEALED_THEN_MASKED','group_counts':{g:len(v) for g,v in groups.items()},
                                    'raw_seal_sha256':sha(OUT/'raw_output_seal.json'),'rubric_sha256':sha(PREP/'rubric18.json'),
                                    'external_judge_calls':0})
    print('MASKED REVIEW READY:3x24 outputs',flush=True)
if __name__=='__main__':main()
