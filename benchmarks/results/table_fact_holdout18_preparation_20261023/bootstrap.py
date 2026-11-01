from common import *
assert not (BASE/'before.json').exists()
names = git('ls-files','--cached','--others','--exclude-standard','-z').decode('utf8').split('\0')
paths={ROOT/n for n in names if n and (ROOT/n).is_file()}
paths.add(ROOT/'.env')
store=ROOT/'data/app_full11_2023_v12_20261017'
paths.update(p for p in store.rglob('*') if p.is_file())
deps=['table_fact_units_offline_20261023/projector.py','table_fact_units_offline_20261023/run.py',
      'table_bundle_delivery_offline_20261022/projector.py','table_fact_answer_full77_20261023/protocol.json',
      'table_fact_answer_full77_20261023/summary.json','table_fact_answer_full77_20261023/generation_performance.json']
paths.update(ROOT/'benchmarks/results'/p for p in deps)
write(BASE/'before.json',{'at':now(),'head':git('rev-parse','HEAD').decode().strip(),
 'index_sha256':sha(ROOT/'.git/index'),'files':{str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)},
 'active_store_files':[str(p.relative_to(ROOT)) for p in store.rglob('*') if p.is_file()]})
(BASE/'git_status_before.bin').write_bytes(git('status','--porcelain=v1','-z','--untracked-files=all'))
write(BASE/'selection_lock.json',{'at':now(),'companies':[
 {'label':'기아','stock_code':'000270','sector':'automotive'},
 {'label':'삼성SDS','stock_code':'018260','sector':'IT services and logistics'},
 {'label':'아모레퍼시픽','stock_code':'090430','sector':'cosmetics'}],
 'period':'2025.12','filing_selection':'Latest annual report, including corrections, submitted by 2026-10-23; exact listed stock identity; no prior evaluated receipt or source hash.',
 'question_allocation':'6 per report: 2 direct multi-axis numeric, 1 calculation, 1 mixed numeric/explanation, 1 narrative relation, 1 bounded unanswerable request. Author from raw source before any retrieval or model outputs.',
 'sampling':'Purposive sector coverage, not random or representative. New questions authored for realistic use; not user logs.',
 'provider_boundary':'Only free DART corpCode/list/document requests explicitly authorized; model/embedding/judge calls 0.',
 'user_source_authorization':'무료 DART 원문 조회·다운로드 허용'})
(BASE/'passport.md').write_text('# Material Passport\n\n- Origin Skill: academic-research-suite / experiment-agent\n- Origin Mode: plan\n- Origin Date: 2026-10-23\n- Verification Status: PREPARING; no generated answers\n- Version Label: holdout18-v1\n- Authorized: local preparation and free DART source acquisition only\n- Model/embedding/judge API calls: 0\n',encoding='utf8')
write(BASE/'ledger_initial.json',{'kind':'initial_instructions','user_words':'추가 호출 없이 기존 평가에 쓰지 않은 보고서 3개로 실사용 질문 18개와 정답 근거·판정 기준을 준비. 모델·검색·프롬프트 고정, 기존 전달64KiB와 표 보강160KiB 각각2회 실행 조건·예상 비용·호출 상한. 기존 구현·.env·v12 store 보존. 후속 응답: 무료 DART 원문 조회·다운로드 허용.'})
print(json.dumps({'protected_files':len(paths),'active_store_files':len(read(BASE/'before.json')['active_store_files'])}))
