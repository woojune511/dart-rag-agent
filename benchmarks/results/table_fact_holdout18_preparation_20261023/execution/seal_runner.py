from common_exec import *
from decimal import Decimal
frozen()
test=load(OUT/'test_result_final.json')
need(test['status']=='PASS' and test['run_sha256']==sha(OUT/'run.py') and test['offline_stage_sha256']==sha(OUT/'offline_stage.py') and test['common_sha256']==sha(OUT/'common_exec.py'),'Stale guard tests')
for name in ['data_contract_validation.json','numeric_contract_validation.json','offline_stage_smoke_hydration.json','preflight_audit.json']:
    need(load(OUT/name)['status']=='PASS','Offline admission '+name)
entries=load(OUT/'embedding_requests.json')
reserve=sum(Decimal(e['reserve']) for e in entries)+(Decimal(98304)*Decimal('2.5')+8192*10)*36/1000000+(Decimal(229376)*Decimal('2.5')+8192*10)*36/1000000
need(reserve<=36,'Saturated bound')
files=['run.py','common_exec.py','offline_stage.py','launch.py','test_runner.py','preflight_data.py','preflight_numeric.py','authorization.json',
 'pricing_revalidation.json','embedding_requests.json','test_result_final.json','data_contract_validation.json','numeric_contract_validation.json',
 'offline_stage_smoke_hydration.json','preflight_audit.json','preservation_before.json']
put(OUT/'runner_freeze.json',{'at':now(),'status':'FROZEN_BEFORE_PAID_CALLS','files':{p:sha(OUT/p) for p in files},
 'preparation_sha256':sha(PREP/'freeze.json'),'max_http_attempts':105,'max_usd':'36','max_wall_seconds':9000,
 'saturated_conservative_reservation_usd':str(reserve),'calls_so_far':0})
put(OUT/'ledger_preflight.json',{'kind':'tool_receipt','step':'bounded_execution_preflight','status':'passed',
 'command':'frozen preparation revalidation;24 mock guard checks;all3768 hydrated-source parity;3report numeric projector;independent native code audit; seal_runner.py',
 'exit_status':0,'retries_used':0,'input_sha256':{'../freeze.json':sha(PREP/'freeze.json')},'output_sha256':sha(OUT/'runner_freeze.json'),
 'gate_tokens':['PROVIDER_FREE_PASS','NO_PAID_CALLS_YET','FROZEN_105_36_9000']})
print('RUNNER SEALED:105 maximum attempts;USD36;9000s; saturated reservation',reserve,flush=True)
