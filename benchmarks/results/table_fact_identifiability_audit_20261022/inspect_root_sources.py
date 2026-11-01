"""Source-bound witness extraction for already documented losses; not a retriever."""
import sys
import json
from pathlib import Path
from io import BytesIO
from collect import ROOT, OUT, RESULTS, load, save, sha, exported
sys.path.insert(0,str(ROOT))
from lxml import etree
from src.processing.financial_parser import _sanitize_xml_like_text

TARGETS={
 'KBF_T2_018': {'20240326000894:625:2':['신용손실충당금전입액'], '20240326000894:1846:5':['신용손실충당금전입액']},
 'SKH_T3_080': {'20240319000684:381:252':['외화환산손실','외화환산이익'],'20240319000684:633:233':['외화환산손실','외화환산이익']},
 'SAM_T3_028': {'20240312000736:319:191':['재고자산평가손실'], '20240312000736:210:82':[]},
 'LGE_T2_052': {'20240314001110:20:1':[], '20240314001110:21:2':['전동공구'], '20240314001110:24:2':['양극재'], '20240314001110:897:3':[]},
 'NAV_T2_006': {'20240318000844:1559:7':['커머스']},
 'CEL_T2_014': {'20240318000913:103:44':['CT-P39','CT-P41','CT-P47'], '20240318000913:108:49':['진행 경과','기타사항']},
}

def norm(text):return ' '.join(str(text).split())

def rank_index(hits):return {h['uid']:i for i,h in enumerate(hits,1)}

def main():
    selected={uid for d in TARGETS.values() for uid in d}
    sources=dict(exported(selected));assert set(sources)==selected
    prep=load(RESULTS/'full77_v12_final_20261018/preparation.json')
    files={r['metadata']['rcept_no']:ROOT/r['path'] for r in prep['reports']}
    trees={}; source_checks={}
    for receipt in {u.split(':')[0] for u in selected}:
        path=files[receipt]; raw=path.read_text('utf-8');sanitized,n=_sanitize_xml_like_text(raw)
        parser=etree.XMLParser(no_network=True,resolve_entities=False,recover=False,huge_tree=True)
        trees[receipt]=etree.parse(BytesIO(sanitized.encode()),parser)
        source_checks[receipt]={'path':str(path.relative_to(ROOT)),'sha256':sha(path),'sanitizer_changes':n,'strict_parse_errors':len(parser.error_log)}
    records={}
    for uid,x in sources.items():
        m=x['metadata'];o=json.loads(m.get('table_object_json') or '{}'); receipt=uid.split(':')[0]
        rec={'uid':uid,'export_locator':x['export_locator'],'text_sha256':x['text_sha256'],
          'metadata':{k:m.get(k) for k in ['company','year','section_path','local_heading','consolidation_scope','period_focus','period_labels','unit_hint','table_source_id','table_view']},
          'header_rows':o.get('header_rows',[]),'row_records_count':len(o.get('rows',[])),
          'value_records_count':len(o.get('values',[])),'table_locator':o.get('source_table_locator'),
          'literal_source_contexts':[],'relevant_rows':[],'text':x['text']}
        if o:
            assert o['source_document_sha256']==source_checks[receipt]['sha256']
            nodes=trees[receipt].xpath(o['source_table_locator']); assert len(nodes)==1
            rec['table_locator_and_document_sha_verified']=True
            for c in o.get('source_contexts',[]):
                nodes=trees[receipt].xpath(c['source_locator']);assert len(nodes)==1
                raw_node=''.join(nodes[0].itertext());a,b=c['source_span']
                exact=raw_node[a:b]==c['source_text'];normalized=norm(raw_node[a:b])==norm(c['source_text'])
                assert c['document_sha256']==source_checks[receipt]['sha256'] and normalized
                if c['relation']!='ancestor_heading':
                    rec['literal_source_contexts'].append({**c,'span_exact':exact,'span_normalized_match':normalized})
            targets=next(d[uid] for d in TARGETS.values() if uid in d)
            for row in o.get('rows',[]):
                if any(t in json.dumps(row,ensure_ascii=False) for t in targets):
                    rec['relevant_rows'].append(row)
        records[uid]=rec
    analyses={}
    variants=[('tokenizer_nori_idf_offline_20261022/results.json',['A12','N12']),('nori_structural_tf_offline_20261022/results.json',['F12']),('table_schema_search_validated_offline_20261022/results.json',['S12'])]
    for rel,arms in variants:
        bycase={r['case_id']:r for r in load(RESULTS/rel)}
        for case,targets in TARGETS.items():
            row=bycase[case]
            case_out=analyses.setdefault(case,{})
            for uid in targets:
                u=case_out.setdefault(uid,{})
                for arm in arms:
                    ranks=rank_index(row['rrf'][arm]);bm=rank_index(row['lexical'][arm]);de=rank_index(row['dense']);p=row['packets'][arm]
                    u[arm]={'dense_rank':de.get(uid),'bm25_rank':bm.get(uid),'rrf_rank':ranks.get(uid),'candidate_present':uid in ranks,
                      'selected':ranks.get(uid,9999)<=12,'packet_present':uid in p['uids'],'byte_omitted':uid in [z if isinstance(z,str) else z.get('uid',z.get('source_id')) for z in p['omitted']]}
    save('root_source_witnesses.json',{'source_checks':source_checks,'targets':TARGETS,'records':records,'saved_ranks':analyses})
    for case,rows in analyses.items():
        print(case)
        for uid,arms in rows.items():print(uid,' '.join(f'{a}:D{x["dense_rank"]}/B{x["bm25_rank"]}/R{x["rrf_rank"]}/P{x["packet_present"]}' for a,x in arms.items()))
    print('source_checks',len(source_checks),'sources',len(records),'verified',sum(x.get('table_locator_and_document_sha_verified',False) for x in records.values()))

if __name__=='__main__':main()
