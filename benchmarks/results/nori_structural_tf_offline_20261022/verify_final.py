"""Verify final artifact consistency and preserve the initial workspace snapshot."""
from collections import Counter
from run import BASE,OUT,ARMS,prior,preserve,save

def main():
    seal=prior.load(OUT/'seal.json')
    assert prior.sha(OUT/'protocol.json')==seal['protocol_sha256']
    for name,h in seal['files'].items():assert prior.sha(OUT.parents[2]/name)==h,name
    results=prior.load(OUT/'results.json')
    original={r['case_id']:r for r in prior.load(BASE/'results.json')}
    assert len(results)==len({r['case_id'] for r in results})==77
    n=0
    for r in results:
        assert r['dense']==original[r['case_id']]['dense']
        assert r['lexical']['N12']==original[r['case_id']]['lexical']['N12']
        assert r['rrf']['N12']==original[r['case_id']]['rrf']['N12']
        for a in ARMS:
            p=prior.load(OUT/f"packets/{r['case_id']}_{a}.json")
            uids=[d['chunk_id'] for d in p['documents']]
            selected=[h['uid'] for h in r['rrf'][a][:12]]
            assert uids==r['packets'][a]['uids']
            assert len(uids)==len(set(uids)) and set(uids)<=set(selected)
            assert len(prior.encoded(p).encode())==r['packets'][a]['bytes']<=65536
            assert set(uids)|set(r['packets'][a]['omitted'])==set(selected)
            assert all(d['context']['rcept_no']==r['report_scope']['rcept_no'] for d in p['documents'])
            n+=1
    audit=prior.load(OUT/'all77_source_audit.json')['cases']
    reviews=prior.load(OUT/'source_review.json')['cases']
    reviewmap={r['case_id']:r['verdict'] for r in reviews}
    assert {r['case_id'] for r in audit if r['historical_citations_newly_lost_vs_N12']}<=set(reviewmap)
    assert len(audit)==77
    table=['| 문항 | 그룹 | 문맥 출처 집합 | 새 과거 인용 유실 | 추가 판정 |','|---|---|---|---:|---|']
    for r in audit:
        label=reviewmap.get(r['case_id'],'기계 감사만; 새 답변 미평가')
        table.append(f"| {r['case_id']} | {r['historical_group']} | {'변경' if r['packet_set_changed'] else '동일'} | {len(r['historical_citations_newly_lost_vs_N12'])} | {label} |")
    report=(OUT/'report.md').read_text(encoding='utf-8')
    assert report.count('<!-- ALL77_TABLE -->')==1
    (OUT/'report.md').write_text(report.replace('<!-- ALL77_TABLE -->','\n'.join(table))+'\n',encoding='utf-8')
    saved=preserve()
    verdict={'status':'PASS','cases':77,'packets_checked':n,'frozen_inputs_unchanged':True,'baseline_exact':True,'dense_exact':True,
        'required_unit_panel':'20/26 -> 20/26','requested_targets_restored':0,'new_historical_citation_loss_cases':7,'bounded_source_review_cases':8,
        'verified_quotes':prior.load(OUT/'quote_verification.json')['quotes_checked'],'preservation':saved,
        'external_model_calls':0,'cost_usd':0,'runtime_edits':0,'app_restarts':0,
        'limits':'Consistency/physical-source checks are not semantic acceptance or whole77 answer evaluation.'}
    save('final_validation.json',verdict)
    save('completion.json',{'status':'COMPLETE_NOT_ADOPTED','reason':'Neither requested target recovered; additional source losses. No further treatment or app change.',
        'external_model_calls':0,'cost_usd':0,'answers_generated':0,'scored_runs':1,'scored_retries':0,'review_cases':8,'report':'report.md'})
    print(prior.encoded(verdict))

if __name__=='__main__':main()
