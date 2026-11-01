"""Validate masked review completeness and visible-source receipts, not semantics."""
from common import *
from collections import Counter

def main():
    need(load(OUT/'execution_result.json')['status']=='COMPLETED','Incomplete execution')
    for p,h in load(OUT/'raw_output_seal.json')['files'].items():need(sha(OUT/p)==h,'Raw output changed')
    issues=[];count=0;receipt_count=0;noncited=[];mismatches=[]
    for group in ('batch1','batch2','batch3'):
        folder=OUT/'masked_review'/group
        items={r['review_id']:r for r in load(folder/'items.json')}
        cases={r['case_id']:r for r in load(folder/'rubric.json')['cases']}
        rows=load(folder/'review.json')['reviews']
        need(len(rows)==len(items)==24 and {r['review_id'] for r in rows}==set(items),'Missing/duplicate masked reviews')
        for r in rows:
            item=items[r['review_id']];need(r['case_id']==item['case_id'],'Case drift')
            need(r['notes'],'Missing review note')
            required={f['id'] for f in cases[r['case_id']]['required_facts']}
            need(len(r['required_facts'])==len(required) and {f['id'] for f in r['required_facts']}==required,'Frozen fact coverage')
            need(all(f['note'] and f['status'] in ('FULFILLED','PARTIAL','OMITTED','INCORRECT','UNRESOLVED') for f in r['required_facts']),'Fact disposition')
            need(all(r[a] in ('PASS','PARTIAL','FAIL','AMBIGUOUS') for a in ('accuracy','completeness','faithfulness')),'Unknown verdict')
            need((r['completeness']=='PASS')==all(f['status']=='FULFILLED' for f in r['required_facts']),'Completeness inconsistent')
            packet=load(folder/item['packet_path']);visible={d['source_id'] for d in packet['documents']}
            cited=set((item.get('answer') or {}).get('cited_source_ids',[]))
            for rec in r.get('receipts',[]):
                sid=rec.get('source_id');receipt_count+=1
                if sid and sid not in visible:issues.append({'review_id':r['review_id'],'issue':'receipt source not visible','source_id':sid})
                elif sid and sid not in cited:noncited.append({'review_id':r['review_id'],'source_id':sid,'note':rec.get('note')})
            if item['structural_errors'] and any(r[a]!='FAIL' for a in ('accuracy','completeness','faithfulness')):
                mismatches.append(r['review_id'])
            count+=1
    need(not issues and not mismatches,'Receipt identity/structural failure review mismatch')
    put(OUT/'review_validation.json',{'status':'PASS','reviews':count,'receipts':receipt_count,
        'unknown_receipt_sources':issues,'structural_failure_mismatches':mismatches,'visible_but_not_cited_receipts_for_parent_review':noncited,
        'meaning':'Visible-source identity only; exact claim support requires source review and adjudication.'})
    print(json.dumps({'status':'PASS','reviews':count,'receipts':receipt_count,'noncited_receipts_flagged':len(noncited)},ensure_ascii=False))
if __name__=='__main__':main()
