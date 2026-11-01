"""Paired source-level audit only; no answer generation/judge calls."""
from collections import Counter
from statistics import mean,median
from urllib.parse import unquote
from run import BASE,OUT,ARMS,prior,save

results=prior.load(OUT/'results.json')
original={r['case_id']:r for r in prior.load(BASE/'results.json')}
by_id={r['case_id']:r for r in results}
panel=prior.load(BASE/'known_witness_panel.json')
panel_rows=[]
changes=[]
for c in panel['cases']:
    r=by_id[c['case_id']]
    units=[]
    for u in c['units']:
        stages={}
        known=set(u['known_witnesses'])
        for a in ARMS:
            pools={'candidate':{h['uid'] for h in r['dense']+r['lexical'][a]},'selected':{h['uid'] for h in r['rrf'][a][:12]},'packet':set(r['packets'][a]['uids'])}
            stages[a]={s:sorted(pool & known) for s,pool in pools.items()}
        assert stages['N12']==u['stages']['N12']
        units.append({**{k:v for k,v in u.items() if k!='stages'},'stages':stages})
        if bool(stages['N12']['packet']) != bool(stages['F12']['packet']):
            changes.append({'case_id':c['case_id'],'unit_id':u['unit_id'],'criterion':u['criterion'],'change':'gain' if stages['F12']['packet'] else 'loss','known_witnesses':sorted(known)})
    panel_rows.append({'case_id':c['case_id'],'role':c['role'],'units':units})
panel_summary={a:{s:{'unit_hits':sum(bool(u['stages'][a][s]) for c in panel_rows for u in c['units']),
                   'all_unit_cases':sum(bool(c['units']) and all(u['stages'][a][s] for u in c['units']) for c in panel_rows)}
                  for s in ('candidate','selected','packet')} for a in ARMS}
save('known_witness_panel.json',{'answerable_cases':10,'required_units':26,'refusal_controls_unscored':2,'summary':panel_summary,'changes':changes,'cases':panel_rows})

grades={r['case_id']:r for r in (prior.json.loads(line) for line in (OUT.parent/'full77_sol_top12_20261020/grades.jsonl').read_text(encoding='utf-8').splitlines())}
audits=[]
review_queue=[]
for r in results:
    cid=r['case_id']
    g=grades[cid]
    cited={unquote(s.partition(':')[2]) for s in g['cited_source_ids']}
    n,f=(set(r['packets'][a]['uids']) for a in ARMS)
    nselected,fselected=({h['uid'] for h in r['rrf'][a][:12]} for a in ARMS)
    nc,fc=({h['uid'] for h in r['dense']+r['lexical'][a]} for a in ARMS)
    lost_cited=sorted((cited & n)-f)
    audit={'case_id':cid,'query':r['query'],'historical_group':g['group'],'historical_note':g['note'],
        'historical_all_three_PASS':all(g[k]=='PASS' for k in ('correctness','completeness','support')),
        'bm25_order_changed':[h['uid'] for h in r['lexical']['N12']]!=[h['uid'] for h in r['lexical']['F12']],
        'candidate_lost':sorted(nc-fc),'candidate_gained':sorted(fc-nc),
        'final12_set_changed':nselected!=fselected,'packet_set_changed':n!=f,
        'packet_order_changed':r['packets']['N12']['uids']!=r['packets']['F12']['uids'],
        'final12_lost':sorted(nselected-fselected),'final12_gained':sorted(fselected-nselected),
        'packet_lost':sorted(n-f),'packet_gained':sorted(f-n),
        'historical_citations_newly_lost_vs_N12':lost_cited,'historical_citations_recovered_vs_N12':sorted((cited & f)-n),
        'historical_citations_missing_N12':sorted(cited-n),'historical_citations_missing_F12':sorted(cited-f),
        'A12_packet_lost_in_F12':sorted(set(original[cid]['packets']['A12']['uids'])-f)}
    audits.append(audit)
    if lost_cited:
        packet=prior.load(OUT/f'packets/{cid}_F12.json')
        prior_packet=prior.load(OUT/f'packets/{cid}_N12.json')
        review_queue.append({'case_id':cid,'query':r['query'],'historical_group':g['group'],'historical_note':g['note'],
            'newly_lost_cited_sources':[d for d in prior_packet['documents'] if d['chunk_id'] in lost_cited],
            'current_packet':packet})
save('all77_source_audit.json',{'scope':'All77 source sets and historical A12 answer citations; primary regression comparison is F12 vs N12. A missing source ID is only a review trigger, not an answer regression.','cases':audits})
save('source_review_queue.json',review_queue)

targets=[]
for r in results:
    for t in r['targets']:
        row=dict(t)
        for a in ARMS:
            bm=next((h['score'] for h in r['lexical'][a] if h['uid']==t['uid']),None)
            row['arms'][a]['bm25_exact_score_ties']=[h['uid'] for h in r['lexical'][a] if h['uid']!=t['uid'] and h['score']==bm]
            dset={h['uid'] for h in r['dense']}
            bset={h['uid'] for h in r['lexical'][a]}
            rank=row['arms'][a]['rrf_rank']
            ahead=[h['uid'] for h in r['rrf'][a][:rank-1]] if rank else []
            row['arms'][a]['ahead_by_stream']={'both':sum(u in dset & bset for u in ahead),'dense_only':sum(u in dset-bset for u in ahead),'bm25_only':sum(u in bset-dset for u in ahead)}
        targets.append(row)
save('target_diagnostics.json',targets)

summary={'cases':77,'arms':{}}
for a in ARMS:
    sizes=[r['packets'][a]['bytes'] for r in results]
    summary['arms'][a]={'known_witness_panel':panel_summary[a],
        'packet_mean_bytes':round(mean(sizes),1),'packet_median_bytes':median(sizes),'packet_max_bytes':max(sizes),
        'cases_with_byte_omissions':sum(bool(r['packets'][a]['omitted']) for r in results),
        'omitted_sources':sum(len(r['packets'][a]['omitted']) for r in results),
        'cases_missing_historical_citations':sum(bool(x['historical_citations_missing_'+a]) for x in audits)}
summary.update({'bm25_order_changed_cases':sum(x['bm25_order_changed'] for x in audits),
    'candidate_set_changed_cases':sum(bool(x['candidate_lost'] or x['candidate_gained']) for x in audits),
    'final12_set_changed_cases':sum(x['final12_set_changed'] for x in audits),'packet_set_changed_cases':sum(x['packet_set_changed'] for x in audits),
    'packet_order_changed_cases':sum(x['packet_order_changed'] for x in audits),
    'new_citation_loss_cases_vs_N12':sum(bool(x['historical_citations_newly_lost_vs_N12']) for x in audits),
    'new_citation_loss_group_counts':dict(Counter(x['historical_group'] for x in audits if x['historical_citations_newly_lost_vs_N12'])),
    'historical_all_three_PASS_new_citation_loss_cases':sum(x['historical_all_three_PASS'] and bool(x['historical_citations_newly_lost_vs_N12']) for x in audits),
    'panel_changes':changes})
save('automated_summary.json',summary)
print(prior.encoded(summary))
