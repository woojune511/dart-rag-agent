"""Seal first, then arm/repetition-masked native source review; no external judge."""
from common_exec import *
import random
frozen()
need(load(OUT/'execution_result.json')['status']=='COMPLETED','All72 answers required before review')
for p,h in load(OUT/'raw_output_seal.json')['files'].items():need(sha(OUT/p)==h,'Raw output seal drift')
answers=[json.loads(x) for x in (OUT/'live/answers.jsonl').read_text('utf8').splitlines()]
need(len(answers)==72 and len({(x['case_id'],x['arm'],x['repeat']) for x in answers})==72,'Response cardinality')
rubric=load(PREP/'rubric.json');cases={c['case_id']:c for c in rubric['cases']}
instructions={
 'task':'Grade every supplied answer against the frozen source-authored rubric and the ACTUAL cited model-visible packet. Do not read mappings, live outputs, other workers, or condition-level results.',
 'disclosure':'Arm and repetition labels hidden; packet shape may reveal treatment. Native Codex review, not independent human or cross-family validation. No external API calls.',
 'accuracy':'PASS if all requested required results/relations are correct and no material false extra claim; PARTIAL for incomplete but partly correct/limited abstention; FAIL for a wrong material result/relation or no correct substantive result. Optional omissions alone never fail.',
 'completeness':'PASS iff every frozen required fact fulfilled; PARTIAL when some are present; FAIL if none. Use frozen IDs, no new mandatory items.',
 'faithfulness':'PASS iff all material factual claims are grounded in actual cited visible text/context/table units; PARTIAL for a limited unsupported noncentral claim; FAIL for unsupported/mislinked core numbers/entities/periods/units or substantive invented relations. A correct gold value or valid ID alone is insufficient. Source text and structured table units may jointly support a claim; no copied-caption-field requirement.',
 'refusal':'For refusal cases require abstained=true, scoped insufficiency, missing operand/relation explained, no fabricated requested result, and any explicitly requested nearest disclosed metric. Do not infer whole-report absence from retrieved absence. Else NOT_APPLICABLE.',
 'facts':'For every required_facts entry: id, status FULFILLED/PARTIAL/OMITTED/INCORRECT/UNRESOLVED, note. Status measures correct fulfillment; citations assessed separately. Preserve criterion ambiguity visibly, never rewrite gold.',
 'evidence':'Read each cited source for every required and material extra claim. Record receipts with source_id plus exact relevant text, context or wire unit coordinates. Wire units reference a local cells array: units=[expanded_row,column,value_index,row_indices,column_indices]. Physical linkage does not certify financial semantics.',
 'invalid_output':'Any structural_errors => accuracy/completeness/faithfulness FAIL; retain answer, never regenerate.',
 'output':'review.json: {reviews:[{review_id,case_id,accuracy,completeness,faithfulness,appropriate_abstention,required_facts:[{id,status,note}],unsupported_claims:[],receipts:[{source_id,locator,quote,note}],notes}],review_limitations:[]}. Axes PASS/PARTIAL/FAIL/AMBIGUOUS. At least one meaningful judgment note; source-less refusals can record packet absence explicitly.',
 'scope':'Only assigned masked_review/batch folder and source XML paths stated in rubric are review input. Shared read_masked.py can display source text or unit dependencies. Write only assigned batch/review.json. No runtime/store/env edits, no network, no model generation.'}
random.Random(2026102318).shuffle(answers)
groups={f'batch{i}':[] for i in (1,2,3)};mapping=[]
for i,a in enumerate(answers,1):
    rid=f'R{i:03d}';group=f'batch{(int(a["case_id"][1:])-1)//6+1}';folder=OUT/'masked_review'/group
    pkt=load(OUT/'packets'/f'{a["case_id"]}_{a["arm"]}.json');put(folder/'packets'/f'{rid}.json',pkt)
    groups[group].append({'review_id':rid,'case_id':a['case_id'],'answer':a['answer'],'raw_text':a['raw_text'],
      'structural_errors':a['structural_errors'],'packet_path':f'packets/{rid}.json'})
    mapping.append({'review_id':rid,'case_id':a['case_id'],'arm':a['arm'],'repeat':a['repeat'],'group':group,
      'attempt':a['attempt'],'response_sha256':sha(OUT/'live'/f'{a["attempt"]:03d}_response.json'),'packet_sha256':sha(folder/'packets'/f'{rid}.json')})
for g,items in groups.items():
    folder=OUT/'masked_review'/g;ids=sorted({x['case_id'] for x in items})
    put(folder/'items.json',items)
    put(folder/'rubric.json',{'common_grading':rubric['common_grading'],'cases':[cases[cid] for cid in ids],
      'raw_source_paths':{cases[cid]['receipt']:str(PREP/'sources'/cases[cid]['receipt']/'original.xml') for cid in ids}})
    put(folder/'instructions.json',instructions)
put(OUT/'review_mapping.json',mapping)
put(OUT/'review_preparation.json',{'status':'SEALED_THEN_MASKED','counts':{k:len(v) for k,v in groups.items()},
 'raw_seal_sha256':sha(OUT/'raw_output_seal.json'),'rubric_sha256':sha(PREP/'rubric.json'),'mapping_sha256':sha(OUT/'review_mapping.json'),
 'masking':'Condition/repetition withheld from fresh workers; representation may reveal arm','external_judge_calls':0})
print('MASKED REVIEW READY:3batches x24 answers',flush=True)
