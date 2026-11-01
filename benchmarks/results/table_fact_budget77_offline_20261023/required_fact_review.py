"""Read saved packets only; preserve the frozen rubric and record bounded review.

This is an evaluator artifact, not a projector or a retrieval/answer experiment.
Semantic verdicts below are manual source-review decisions. Values in this file
are never used to select, project, prioritize, or deliver experiment units.
"""
from __future__ import annotations
import copy
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
OLD = OUT.parent / 'table_fact_units_offline_20261023'
T12 = OUT.parent / 'table_bundle_delivery_offline_20261022'
sys.path.insert(0, str(ROOT))

def read(p):
    return json.loads(p.read_text(encoding='utf-8'))

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def canonical(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'))

def without_appendix(p):
    x=copy.deepcopy(p)
    for d in x['documents']:
        d.pop('table_fact_units', None)
    return x

contract=read(OUT/'evaluation_contract.json')
supplement=read(OUT/'evaluation_supplement.json')
prior=read(OLD/'postrun_required_fact_review.json')
results={r['case_id']:r for r in read(OUT/'results.json')}
old_results={r['case_id']:r for r in read(OLD/'results.json')}
projections=read(OLD/'projections.json')
sources=read(OLD/'source_checks.json')
assert digest(OUT/'evaluation_contract.json') == digest(OLD/'evaluation_contract.json') == '6df6519b4ac617579d1d9cdf92589dfbcc7de013d493f869115427b75f7ecee6'
assert digest(OUT/'evaluation_supplement.json') == digest(OLD/'evaluation_supplement.json') == '05f878a9eebaebbabfac8a35dd99d16be428b8fc330e223267ee644c3692a4c0'

packets={}
decoded={}
checks={}
def decode(cid, arm):
    packet=read(OUT/'packets'/f'{cid}_{arm}.json')
    decisions={d['uid']:d for d in results[cid]['arms'][arm]['decisions']}
    units={}
    inventory=[]
    for doc in packet['documents']:
        uid=doc['chunk_id'];w=doc.get('table_fact_units')
        if not w:
            continue
        decision=decisions[uid];pool=decision['cell_pool_locators']
        frame={k:v for k,v in w.items() if k not in ('cells','units')}
        projection=projections[uid]['projection']
        assert projection and len(pool)==len(w['cells'])
        for loc,cell in zip(pool,w['cells']):
            assert projection['cells'][loc]==cell
        attached={u['wire_unit_index']:u for u in decision['units'] if u['status']=='attached'}
        assert len(attached)==len(w['units'])
        by_id={u['unit_id']:u for u in projection['units']}
        for i,(r,c,v,ra,ca) in enumerate(w['units']):
            saved=attached[i];p=by_id[saved['unit_id']]
            assert [r,c]==p['at'] and pool[v]==p['value']
            assert [pool[a] for a in ra]==p['row_axes']
            assert [pool[a] for a in ca]==p['column_axes']
            key=uid+'|'+saved['unit_id']
            units[key]={'chunk_uid':uid,'unit_id':saved['unit_id'],'at':[r,c],
                'value':{'locator':pool[v],'cell':w['cells'][v]},
                'row_axes':[{'locator':pool[a],'cell':w['cells'][a]} for a in ra],
                'column_axes':[{'locator':pool[a],'cell':w['cells'][a]} for a in ca],
                'frame':frame}
        inventory.append({'chunk_uid':uid,'table_locator':frame['table_locator'],
            'source_contexts':frame.get('literal_source_contexts',[]),
            'transmitted_units':len(w['units']),
            'row_axis_vocabulary':list(dict.fromkeys(w['cells'][i][4] for u in w['units'] for i in u[3]))})
    return packet,units,inventory

all_inventory={}
for cid,r in results.items():
    baseline=read(OLD/'packets'/f'{cid}_A12.json')
    for arm in ('64KiB','160KiB'):
        p,u,i=decode(cid,arm);packets[cid,arm]=p;decoded[cid,arm]=u;all_inventory[cid,arm]=i
        assert without_appendix(p)==baseline
        assert len(u)==r['arms'][arm]['attached_units']
        assert r['selected12']==old_results[cid]['selected12']
        assert r['delivered_ids']==old_results[cid]['delivered_ids']
        assert r['candidate_order_score_sha256']==old_results[cid]['candidate_order_score_sha256']
    assert (OUT/'packets'/f'{cid}_64KiB.json').read_bytes()==(OLD/'packets'/f'{cid}_FCT12.json').read_bytes()
    u64=decoded[cid,'64KiB'];u160=decoded[cid,'160KiB']
    lost=sorted(set(u64)-set(u160));added=sorted(set(u160)-set(u64))
    changed=[k for k in set(u64)&set(u160) if u64[k]!=u160[k]]
    assert not lost and not changed
    assert added==sorted(r['unit_changes']['added'])
    checks[cid]={'original_A12_text_context_ids_order_preserved_both_arms':True,
        'previous_FCT12_64_packet_bytes_exact':True,'selected12_and_candidate_order_score_preserved':True,
        'original_document_count':len(baseline['documents']),
        '64_units':len(u64),'160_units':len(u160),'retained_units':len(u64),
        'added_units':len(added),'lost_64_units':lost,'changed_64_payloads':changed,
        'packet_bytes':{a:r['arms'][a]['packet_bytes'] for a in ('64KiB','160KiB')},
        'new_numeric_unit_count_is_not_new_required_fact_count':True}

trees={};source_rechecks=[];normalizations=[]
def source_tree(receipt):
    if receipt not in trees:
        from lxml import etree
        from src.processing.financial_parser import _sanitize_xml_like_text
        info=sources[receipt];raw=(ROOT/info['path']).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==info['sha256']
        clean,_=_sanitize_xml_like_text(raw.decode('utf-8'))
        trees[receipt]=etree.fromstring(clean.encode('utf-8'),etree.XMLParser(no_network=True,resolve_entities=False,recover=False,huge_tree=True)).getroottree()
        source_rechecks.append({'receipt':receipt,'path':info['path'],'sha256':info['sha256'],'hash_match':True,'strict_xml_parse_after_existing_sanitizer':True})
    return trees[receipt]

def geometry(tree, table_locator):
    table=tree.xpath(table_locator)[0];occupied=set();out={}
    for r,tr in enumerate(table.xpath('.//TR')):
        c=0
        for cell in tr:
            if cell.tag not in ('TH','TD','TE','TU'):continue
            while (r,c) in occupied:c+=1
            rs=int(cell.get('ROWSPAN','1'));cs=int(cell.get('COLSPAN','1'))
            out[tree.getpath(cell)]=[r,c,rs,cs,''.join(cell.itertext()).strip()]
            for rr in range(r,r+rs):
                for cc in range(c,c+cs):occupied.add((rr,cc))
            c+=cs
    return out

def at_record(cid,uid,at):
    actual=next(u for u in decoded[cid,'160KiB'].values() if u['chunk_uid']==uid and u['at']==at)
    tree=source_tree(uid.split(':')[0]);geom=geometry(tree,actual['frame']['table_locator'])
    for item in [actual['value']]+actual['row_axes']+actual['column_axes']:
        src=geom[item['locator']];wire=item['cell']
        assert src[:4]==wire[:4]
        if src[4]!=wire[4]:
            assert re.sub(r'\s+',' ',src[4])==re.sub(r'\s+',' ',wire[4])
            normalizations.append({'locator':item['locator'],'source':src[4],'wire':wire[4],'kind':'whitespace_only'})
    contexts=[]
    for ctx in actual['frame']['literal_source_contexts']:
        elem=tree.xpath(ctx['source_locator'])[0]
        text=''.join(elem.itertext());lo,hi=ctx['source_span']
        assert text[lo:hi]==ctx['source_text']
        contexts.append({**ctx,'exact_source_span_match':True})
    key=uid+'|'+actual['unit_id']
    prior_decisions={d['uid']:d for d in results[cid]['arms']['64KiB']['decisions']}
    before=next((u for u in prior_decisions[uid].get('units',[]) if u['unit_id']==actual['unit_id']),None)
    return {**actual,'source_gate':'SOURCE_LITERAL_COORDINATES_AND_CONTEXT_SPANS_RECHECKED',
        '64KiB_delivery_gate':'ACTUALLY_DELIVERED' if key in decoded[cid,'64KiB'] else 'NOT_DELIVERED',
        '64KiB_decision':before,'160KiB_delivery_gate':'ACTUALLY_DELIVERED',
        'contexts':contexts,'numeric_string_match_used_as_semantic_verdict':False}

new_evidence={
    'HYU_T3_072':[
        at_record('HYU_T3_072','20240313001451:1246:4',[143,12]),
        at_record('HYU_T3_072','20240313001451:1246:4',[143,13]),
        at_record('HYU_T3_072','20240313001451:1246:4',[143,15])],
    'MIX_T3_063':[
        at_record('MIX_T3_063','20240318000844:384:260',[7,1]),
        at_record('MIX_T3_063','20240318000844:384:260',[7,20])],
    'KAK_T3_055':[
        at_record('KAK_T3_055','20240418000375:733:592',[15,2])]
}

notes={
 'POS_T1_057':'64/160 packets have identical evidence. Current/prior financial income-cost and borrowing-cost capitalization tables contain no source-equivalent connected operating-income row. 1186:24 remains saved BM25 rank18/RRF28, outside the frozen selected12; this is selection loss, not blanket candidate absence.',
 'SKH_T1_060':'All180 added units were inspected by physical table and axes. They come only from connected/separate current/prior borrowing tables281:152,531:131,282:153,535:135,278:149,532:132. None supplies connected closing PPE52,704,853 or intangible3,834,567. Existing277:148 three named debt operands remain.',
 'HYU_T3_072':'At160, Motional row143 in selected1246:4 supplies closing ownership25.81%, carrying1,294,367백만원 and recent-year netprofit-803,742백만원. These are the 2023.12.31 타법인출자 현황(상세) alternative. Literal frame does not say 별도; do not claim separate-financial-statement scope was literally certified, or mix with connected26%/700,691. Missing named revenue1,775, OCI12,115 and comprehensive income-791,627 keep the frozen four-item profit_summary incomplete.',
 'SKI_T1_068':'Battery operating loss(581,816), total1,903,886 and literal백만원 caption on1713:6 were already delivered at64 and remain identical at160. Caption is a prior T12/FCT64 axis recovery, not a new cap160 value or axis recovery.',
 'MIX_T3_063':'New current table384:260 supplies A Holdings15,338,412,557 and Mirae Asset-Naver341,924,825천원 in the 장부금액 row with company columns and 당기 bound caption. Prior64 has only previous-period numeric table396:272 and clipped current nonnumeric rows. No current profit table426:302 or equivalent is present:425:301 is an introduction. book_entities conditional criterion improves, profit_entities remains absent; HOLD and ranking-population uncertainty remain. No absolute-year inference from filing metadata.',
 'KAK_T3_055':'New source-bound acquisition table733:592 adds 식별가능한 순자산/무형자산 e.g. 에스엠엔터테인먼트 외29개사608,409,502천원. Earlier original733 retained only tail liabilities/noncontrolling-interest/goodwill rows; these new intangible cells are partial R2 evidence, not just duplicate goodwill. R2 also requires whole beginning/end and business-combination movement with totals/goodwill columns; that table is absent. Existing771:630 revenue and original733 goodwill evidence are preserved. HOLD remains.',
 'CEL_T2_073':'All10 added units belong to Celltrion Pharm product/service totals and older-year service columns in136:12, under 연결대상 주요 종속회사/(1)셀트리온제약, not a group foreign-sales numerator. Original group revenue/direct-sales narrative remains. Overseas-share definition and numerator gap are unchanged; no new conditional required recovery.',
 'KBF_T1_017':'Added quantitative details do not resolve the frozen bank/group NIM interpretation or displayed-year difference. Original1842:1 bank+card2.44/2.30 and separately reported0.13%p remain. HOLD preserved; no new required recovery.',
 'KBF_T2_043':'Existing fee operands and WM-related scoped evidence retained.160 restores T12 bound summary백만원 and AUM십억원 captions omitted atFCT64; it does not settle noninterest definition or identify groupAUM as WM-only performance. HOLD remains.',
 'HYU_T3_036':'Original333:191 connected warranty increase2,175,691 and183:41 accounting estimate explanation remain. Added table cells/axes do not resolve inherited connected/separate answer-key conflict. HOLD remains.',
 'SAM_T1_001':'Revenue and operating income were already present.160 restores the123:2 explicit 제55기→2023.01.01~12.31 calendar/unit caption previously supplied byT12 but omitted atFCT64. Count calendar binding enrichment, not new numeric recovery.',
 'MIX_T3_048':'Actual paid dividend9,864,474백만원 and return-policy prose were already available. Added rows/context are enrichment; no new required recovery.',
 'CEL_T3_040':'The connected prior-period inventory-loss/reversal/disposal cells and their axes already passed the frozen source review. Same actual source units persist; no new recovery and no answering claim.'
}

current=[]
for pc in prior['current4']:
    cid=pc['case_id'];units=[]
    for u in pc['units']:
        after=u['FCT12_required_evidence_present'];status='PRESERVED' if after else 'STILL_ABSENT'
        e=[]
        if cid=='HYU_T3_072':
            if u['unit_id'] in ('ownership','carrying'):
                after=True;status='NEW_SOURCE_BOUND_INVESTMENT_TABLE_ALTERNATIVE'
                e=[new_evidence[cid][0 if u['unit_id']=='ownership' else 1]]
            else:
                after=False;status='PARTIAL_COMPONENT_ONLY_FULL_REQUIRED_SUMMARY_ABSENT';e=[new_evidence[cid][2]]
        preserved_gates=[]
        for g in u.get('FCT12_gate_reviews',[]):
            if g.get('unit_id') and g.get('chunk_uid'):
                key=g['chunk_uid']+'|'+g['unit_id']
                if key in decoded[cid,'64KiB']:
                    assert key in decoded[cid,'160KiB']
                    preserved_gates.append({'chunk_uid':g['chunk_uid'],'unit_id':g['unit_id'],'at':g.get('at'),'wire_value_axes_frame_identical':True})
        units.append({'unit_id':u['unit_id'],'criterion':u['criterion'],
            'A12_present':u['A12_required_evidence_present'],'T12_present':u['T12_required_evidence_present'],
            '64KiB_present':u['FCT12_required_evidence_present'],'160KiB_present':after,
            '160KiB_status':status,'new_source_evidence':e,'retained_source_units':preserved_gates,
            'prior_source_review_reference':str(OLD.relative_to(ROOT)/'postrun_required_fact_review.json'),
            'answer_effect':'NOT_MEASURED_NO_GENERATION'})
    current.append({'case_id':cid,'baseline_grade_unchanged':pc['baseline_grade'],'units':units,
        'full_required_evidence_64':all(u['64KiB_present'] for u in units),
        'full_required_evidence_160':all(u['160KiB_present'] for u in units),
        'case_delta':'PARTIAL_EVIDENCE_RECOVERY' if cid=='HYU_T3_072' else 'NO_NEW_REQUIRED_RECOVERY',
        'finding':notes[cid],'preservation':checks[cid],
        'actual_160_physical_table_inventory':all_inventory[cid,'160KiB']})

legacy=[]
for pc in prior['legacy26_panel']:
    cid=pc['case_id'];units=[]
    for u in pc['units']:
        present=u['FCT12_required_evidence_present']
        witnesses=[]
        for g in u['FCT12_gate_reviews']:
            if not(g.get('chunk_uid') and g.get('unit_id')):continue
            key=g['chunk_uid']+'|'+g['unit_id']
            witnesses.append({'chunk_uid':g['chunk_uid'],'unit_id':g['unit_id'],'at':g.get('at'),
                '64_delivered':key in decoded[cid,'64KiB'],'160_delivered':key in decoded[cid,'160KiB'],
                'source_and_prior_verdict_reference':'prior_review.legacy26_panel.'+cid+'.'+u['unit_id']})
        units.append({'unit_id':u['unit_id'],'criterion':u['criterion'],'value_or_relation':u['value_or_relation'],
            'axes':u['axes'],'A12_present':u['A12_required_evidence_present'],'T12_present':u['T12_required_evidence_present'],
            '64KiB_present':present,'160KiB_present':present,
            'delta':'PRESERVED' if present else 'STILL_ABSENT',
            'actual_unit_delivery':witnesses,'original_body_preserved':True,
            'original_body_can_supply_requirement_when_no_added_unit':True,
            'source_semantics_inherited_from_frozen_prior_review_not_fresh_answer_grade':True})
    legacy.append({'case_id':cid,'group':pc['group'],'units':units,'finding':notes.get(cid,'Existing frozen source-bound facts and any necessary original narrative are preserved; no new required-unit recovery in this panel.'),'preservation':checks[cid]})

restored_contexts=[]
for loss in prior['T12_enrichment_losses_with_original_fact_preservation']:
    cid=loss['case_id'];uid=loss['chunk_uid']
    d64=next(d for d in packets[cid,'64KiB']['documents'] if d['chunk_id']==uid)
    d160=next(d for d in packets[cid,'160KiB']['documents'] if d['chunk_id']==uid)
    assert 'table_fact_units' not in d64 and 'table_fact_units' in d160
    frame=d160['table_fact_units'];tree=source_tree(uid.split(':')[0])
    for ctx in frame['literal_source_contexts']:
        lo,hi=ctx['source_span'];assert ''.join(tree.xpath(ctx['source_locator'])[0].itertext())[lo:hi]==ctx['source_text']
    restored_contexts.append({**loss,'160KiB_appendix_restored':True,
        'actual_source_contexts':frame['literal_source_contexts'],'new_required_numeric_fact':False,
        'absolute_calendar_binding_restored':cid=='SAM_T1_001','required_original_evidence_loss':False})

current_by={x['case_id']:x for x in current}
all_cases=[]
for c in contract['cases']:
    cid=c['case_id'];changed=checks[cid]['added_units']>0;criteria=[]
    for criterion in c['required_units']:
        record={'frozen_criterion':copy.deepcopy(criterion),'original_evidence_preserved':True,
            'FCT64_enrichment_preserved':True,'new_answer_verdict':'NOT_MEASURED_NO_GENERATION',
            '64KiB_requirement_state':'INHERITED_BASELINE_NOT_RELABELED',
            '160KiB_requirement_state':'SAME_REQUIRED_EVIDENCE_NO_LOSS',
            'delta':'CONTEXT_ENRICHMENT_OR_DUPLICATION_NO_NEW_REQUIRED_RECOVERY' if changed else 'EVIDENCE_IDENTICAL_TO64'}
        if cid in current_by:
            u=next(u for u in current_by[cid]['units'] if u['unit_id']==criterion['unit_id'])
            record.update({'64KiB_requirement_state':'PRESENT' if u['64KiB_present'] else 'ABSENT_OR_INCOMPLETE',
                '160KiB_requirement_state':u['160KiB_status'],'delta':u['160KiB_status'],
                'specific_review':'postrun_required_fact_review.json.current4.'+cid+'.'+u['unit_id']})
        elif cid=='MIX_T3_063':
            book=criterion['unit_id']=='book_entities'
            record.update({'64KiB_requirement_state':'ABSENT',
                '160KiB_requirement_state':'CONDITIONAL_CURRENT_COMPANY_BOOK_VALUES_PRESENT' if book else 'STILL_ABSENT',
                'delta':'NEW_CONDITIONAL_REQUIRED_VALUES_HOLD_UNCHANGED' if book else 'NO_RECOVERY',
                'source_evidence':new_evidence[cid] if book else [],'hold_lifted':False})
        elif cid=='KAK_T3_055' and criterion['unit_id']=='R2':
            record.update({'64KiB_requirement_state':'PARTIAL_ACQUISITION_GOODWILL_ONLY',
                '160KiB_requirement_state':'PARTIAL_ACQUISITION_INTANGIBLE_PLUS_GOODWILL_NO_BEGIN_END_MOVEMENT',
                'delta':'NEW_COMPONENT_ONLY_NOT_FULL_REQUIRED_UNIT','source_evidence':new_evidence[cid],'hold_lifted':False})
        elif c['group']=='diagnostic_or_hold':
            record['hold_lifted']=False
            record['delta']='HOLD_EVIDENCE_PRESERVED_NO_NEW_FULL_CRITERION_RECOVERY'
        criteria.append(record)
    if c['group']=='refusal':disposition='ORIGINAL_EVIDENCE_PRESERVED_REFUSAL_BEHAVIOR_NOT_RETESTED'
    elif cid in current_by:disposition=current_by[cid]['case_delta']
    elif c['group']=='diagnostic_or_hold':disposition='HOLD_RETAINED_CONDITIONAL_EVIDENCE_ONLY'
    else:disposition='HISTORICAL_PASS_EVIDENCE_PRESERVED_NOT_FRESH_ANSWER_PASS'
    all_cases.append({'case_id':cid,'group':c['group'],'question_unchanged':c['question'],
        'historical_answer_grade_unchanged':c['baseline_sol12_grade'],
        'historical_all_axes_pass':c['baseline_all_axes_pass'],'review_disposition':disposition,
        'existing_hold_reason_unchanged':c['existing_hold_reason'],
        'preservation':checks[cid],'required_criteria':criteria,
        'case_interpretation':notes.get(cid,'Original evidence is preserved exactly. Added numeric cells and attached source contexts were not treated as newly correct answers or an automatic semantic PASS.'),
        'added_physical_table_inventory':[
            {**i,'added_unit_count':sum(k not in decoded[cid,'64KiB'] and v['chunk_uid']==i['chunk_uid'] for k,v in decoded[cid,'160KiB'].items())}
            for i in all_inventory[cid,'160KiB'] if any(k not in decoded[cid,'64KiB'] and v['chunk_uid']==i['chunk_uid'] for k,v in decoded[cid,'160KiB'].items())]})

assert len(all_cases)==77 and sum(len(c['required_criteria']) for c in all_cases)==154
summary={'cases':77,'frozen_criteria':154,'original_packets_preserved':77,'exact_previous64_packet_replays':77,
    'baseline_group_counts':dict(Counter(c['group'] for c in contract['cases'])),
    '64_units':sum(x['64_units'] for x in checks.values()),'retained64_units':sum(x['retained_units'] for x in checks.values()),
    'added160_units':sum(x['added_units'] for x in checks.values()),'lost64_units':0,'changed64_payloads':0,
    'cases_with_added_units':sum(x['added_units']>0 for x in checks.values()),
    'current4_new_complete_cases':0,'current4_new_partial_recovery_cases':['HYU_T3_072'],
    'current4_new_complete_required_units':['HYU_T3_072:ownership','HYU_T3_072:carrying'],
    'current4_new_profit_component_not_complete_requirement':'HYU_T3_072:-803,742 recent-year netprofit only',
    'current4_already_complete_SKI_currency_axis_retained':True,
    'hold_conditional_new_complete_unit':['MIX_T3_063:book_entities'],
    'hold_new_partial_component_only':['KAK_T3_055:R2 acquisition identifiable intangible assets'],
    'hold_status_lifted':0,'legacy_common20_present_64':18,'legacy_common20_present_160':18,
    'legacy_HOLD6_present_64':6,'legacy_HOLD6_present_160':6,
    'restored_T12_context_enrichment_documents':3,
    'new_answer_accuracy_completeness_support_refusal_scores':'NOT_MEASURED_NO_GENERATION'}
limits=[
    'Saved-output reviewer had prior development exposure, including the single Motional160 result; not blinded or held out.',
    'The154 frozen criteria are retained case by case. Preservation is proven by exact original packet and unit payload identity. This is not154 new semantic PASS judgements.',
    'Manual source interpretation is bounded to current4, inherited26-unit panel, all changed-HOLD cases, and restored contexts. Prior PASS answers were not regenerated or regraded.',
    'Additional physical-table numeric values do not by themselves count as required fact recovery. Rows, column paths, period/scope/unit context and same-source attribution were examined for claimed gains.',
    '당기/전기/제N기 are retained source periods. No calendar year or scope is assigned from global year/period_focus/unit_hint metadata.',
    'Motional alternative is labelled 타법인출자표 기준. Its bound literal frame does not explicitly label 별도; no literal separate-financial-statement certification or connected26%/700,691 recovery is claimed.',
    'HOLD definitions, ranking population and answer-key conflicts remain unresolved; conditional gains do not enlarge common46 denominator.',
    'No model, provider, retrieval, generation, store, environment, application restart or projector rerun was performed by this review. Larger contexts may affect model errors, which this provider-free review cannot measure.'
]
review={'schema_version':'table_fact_budget_required_review_v1','status':'COMPLETED_BOUNDED_SOURCE_REVIEW',
    'date':'2026-10-23','review_role':'Development-exposed evaluator; actual packet/source audit, no answer grading.',
    'input_hashes':{str(p.relative_to(ROOT)):digest(p) for p in [OUT/'evaluation_contract.json',OUT/'evaluation_supplement.json',OUT/'results.json',OLD/'postrun_required_fact_review.json',OLD/'projections.json']},
    'summary':summary,'current4':current,'legacy26_panel':legacy,
    'additional_HOLD_evidence':{cid:{'finding':notes[cid],'source_evidence':new_evidence.get(cid,[])} for cid in ['MIX_T3_063','KAK_T3_055','CEL_T2_073','KBF_T1_017','KBF_T2_043','HYU_T3_036']},
    'restored_T12_enrichment_not_new_numeric_recovery':restored_contexts,
    'source_files_independently_rechecked_this_review':source_rechecks,
    'source_normalizations':normalizations,'source_errors':[],
    'prior_source_rechecks_reused_by_exact_payload_identity':{'report_sha256':digest(OLD/'postrun_required_fact_review.json'),'original_target_checks':prior['target_source_unit_checks_count']},
    'full77_matrix':'all77_evidence_review.json','limits':limits}
matrix={'schema_version':'table_fact_budget_all77_evidence_v1','status':'COMPLETED_PRESERVATION_MATRIX_NOT_ANSWER_EVAL',
    'frozen_contract_sha256':digest(OUT/'evaluation_contract.json'),'summary':summary,'cases':all_cases,'limits':limits}
for filename,obj in [('postrun_required_fact_review.json',review),('all77_evidence_review.json',matrix)]:
    with (OUT/filename).open('x',encoding='utf-8') as f:
        json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps(summary,ensure_ascii=False))
