"""Audit completed provider receipts and preservation without new calls."""
from common import *
from decimal import Decimal
from run import entries,Guard,CAP,MAX_CALLS,WALL,MODEL

def main():
    result=load(OUT/'execution_result.json');need(result['status']=='COMPLETED','Execution did not finish')
    seal=load(OUT/'raw_output_seal.json')
    for p,h in seal['files'].items():need(sha(OUT/p)==h,'Raw output changed')
    ledger=[json.loads(l) for l in (OUT/'live/ledger.jsonl').read_text('utf8').splitlines()]
    planned=entries();outputs=[json.loads(l) for l in (OUT/'live/answers.jsonl').read_text('utf8').splitlines()]
    byattempt={r['attempt']:r for r in outputs}
    groups={kind:[r for r in ledger if r['event']==kind] for kind in ('dispatch','http_result','settled')}
    need(all(len(v)==72 for v in groups.values()) and len(outputs)==72,'Ledger cardinality')
    cost=Decimal(0);models=set();total_in=total_out=0
    # Access pure response/accounting method without allocating a Guard output path.
    auditor=object.__new__(Guard)
    for n,e in enumerate(planned,1):
        prefix=f'{n:03d}';request=load(OUT/'live'/f'{prefix}_request.json');raw=load(OUT/'live'/f'{prefix}_response.json')
        need(request==e['body'] and digest(request)==e['body_sha256'],'Executed body differs from frozen request')
        dispatch=groups['dispatch'][n-1];settled=groups['settled'][n-1];http=groups['http_result'][n-1]
        need(dispatch['attempt']==settled['attempt']==http['attempt']==n,'Attempt ordering')
        need(dispatch['label']==settled['label']==e['label'] and http['http_status']==200,'Endpoint/label execution result')
        need(load(OUT/'live'/f'{prefix}_response.json')==json.loads((OUT/'live'/f'{prefix}_response_raw.bin').read_bytes()),'Response parse differs from raw bytes')
        measured,usage=auditor.usage(raw,e)
        need(measured==Decimal(settled['estimated_usd'])==Decimal(byattempt[n]['estimated_usd']),'Settled price mismatch')
        need(usage==settled['usage']==byattempt[n]['usage'],'Usage mismatch')
        answer=auditor.answer(raw,e)
        need(all(byattempt[n][k]==v for k,v in answer.items()),'Saved answer drift')
        cost+=measured;total_in+=usage['input_tokens'];total_out+=usage['output_tokens'];models.add(raw['model'])
    need(cost==Decimal(result['usage_estimated_usd'])<=CAP and result['attempts']==MAX_CALLS and result['elapsed_seconds']<=WALL,'Cap breach')
    need(not Decimal(result['unsettled_reserved_usd']) and models=={MODEL},'Unsettled liability/model drift')
    preservation=frozen();runner_frozen()
    review=load(OUT/'review_validation.json');need(review['status']=='PASS' and review['reviews']==72,'Incomplete review')
    summary=load(OUT/'summary.json');need(summary['primary_answerable']['A']['n']==summary['primary_answerable']['C']['n']==30,'Primary denominator')
    need(summary['refusals']['A']['n']==summary['refusals']['C']['n']==6,'Refusal denominator')
    put(OUT/'closeout_validation.json',{'status':'PASS','attempts':72,'successes':72,'failed_requests':0,'retries':0,
        'exact_executed_request_bodies':72,'sealed_raw_responses':72,'fully_reviewed_outputs':72,
        'observed_response_models':sorted(models),'input_tokens':total_in,'output_tokens':total_out,
        'usage_estimated_usd':str(cost),'cost_cap_usd':str(CAP),'elapsed_generation_seconds':result['elapsed_seconds'],
        'generation_wall_seconds_cap':WALL,'external_judge_calls':0,'embedding_calls':0,'new_retrievals':0,
        'preservation':preservation,'app_restarts':0,'semantic_limit':'Source reviews are bounded same-family judgments; schema/receipt checks do not independently prove semantic correctness.'})
    print('CLOSEOUT PASS:72 exact requests/responses,72 reviewed; cost',cost,'protected files unchanged',flush=True)
if __name__=='__main__':main()
