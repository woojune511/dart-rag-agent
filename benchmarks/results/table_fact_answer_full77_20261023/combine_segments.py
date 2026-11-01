"""Index both sealed segments after completion; never overwrite raw provider outputs."""
from pathlib import Path
import importlib.util
from decimal import Decimal
import json

OUT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('frozen_full77',OUT/'run.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

def main():
    segments=[OUT/'live',OUT/'resume01/live']
    entries={(r['case_id'],r['arm']):r for r in b.load(OUT/'requests.json')}
    rows=[];response_ids=[];refs={};dispatches=[]
    for segment_index,folder in enumerate(segments):
        for name,h in b.load(folder/'raw_seal.json')['files'].items(): b.need(b.sha(folder/name)==h,'Raw file drift '+name)
        refs[str(folder.relative_to(OUT))]=b.sha(folder/'raw_seal.json')
        part=[json.loads(x) for x in (folder/'answers.jsonl').read_text('utf-8').splitlines()]
        expected_attempts=list(range(1,44)) if segment_index==0 else list(range(45,310))
        b.need([r['attempt'] for r in part]==expected_attempts,'Segment success partition')
        rows.extend(part)
        for r in part:
            b.need(r['label']==f"{r['case_id']}:{r['arm']}:r{r['repetition']}",'Answer label drift')
            b.need(b.load(folder/f"{r['attempt']:03d}_request.json")==entries[r['case_id'],r['arm']]['body'],'Saved request drift')
            response_ids.append(b.load(folder/f"{r['attempt']:03d}_response.json")['id'])
        dispatches.extend(json.loads(x) for x in (folder/'ledger.jsonl').read_text('utf-8').splitlines() if json.loads(x)['event']=='dispatch')
    result=b.load(segments[1]/'execution_result.json')
    b.need(result['status']=='COMPLETED' and result['completed']==308 and result['attempts']==309,'Continuation not complete')
    bylabel={r['label']:r for r in rows}
    schedule=b.load(OUT/'schedule.json')
    b.need(len(rows)==len(bylabel)==len(set(response_ids))==308,'Answer identity/cardinality')
    b.need(set(bylabel)=={r['label'] for r in schedule},'Schedule coverage')
    b.need(len(dispatches)==309 and len({r['attempt'] for r in dispatches})==309,'Attempt accounting')
    actual=sum(Decimal(r['estimated_usd']) for r in rows)
    b.need(actual==Decimal(result['estimated_usd']),'Cost sum mismatch')
    folder=OUT/'combined';folder.mkdir(exist_ok=False)
    for r in schedule:b.append(folder/'answers.jsonl',bylabel[r['label']])
    b.put(folder/'origin.json',{'raw_seals':refs,'unique_success_response_ids':308,'attempts':309,'failed_attempt':44,'failed_label':'SAM_T4_070:A:r1','replacement_attempt':45,'rule':'All43 prior successes retained; exactly265 authorized continuation answers; no quality-based selection.'})
    aggregate=dict(result)
    w1=b.load(OUT/'watchdog_result.json');w2=b.load(OUT/'resume01/watchdog_result.json')
    aggregate.update(elapsed_seconds=b.load(segments[0]/'execution_result.json')['elapsed_seconds']+result['elapsed_seconds'],
                     aggregate_active_process_seconds=w1['elapsed_seconds']+w2['elapsed_seconds'],
                     provider_failures=1,authorized_replacements=1,successful_answers=308,
                     unsettled_reservation_usd=result['prior_unsettled_reservation_usd'],
                     total_cost_with_uncertain_reservation_usd=str(actual+Decimal(result['prior_unsettled_reservation_usd'])),
                     review_status='NOT_YET_GRADED')
    b.put(folder/'execution_result.json',aggregate)
    b.put(folder/'raw_seal.json',{'at':b.now(),'files':{p.name:b.sha(p) for p in folder.iterdir() if p.is_file()}})
    print('COMBINED308;309attempts;unique_response_ids308;USD',actual,flush=True)

if __name__=='__main__':main()
