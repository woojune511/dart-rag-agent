"""Audit saved packets against raw XML, with independent geometry/axis helpers.

No projector, retrieval or answer generation is executed. Physical validation is
not certification of the entity, reporting period, scope or financial meaning.
"""
import copy
import gzip
import hashlib
import json
import sys
from collections import defaultdict
from io import BytesIO
from pathlib import Path
import run as harness

OUT,ROOT,BASE=harness.OUT,harness.ROOT,harness.BASE
load,save,sha,encoded=harness.load,harness.save,harness.sha,harness.encoded
check=harness.module('independent_prior_geometry',harness.BUDGET/'postrun_boundary_check.py')

def main():
    harness.frozen()
    results=load(OUT/'results.json')
    projections=load(harness.FACT/'projections.json')
    projections.update(load(OUT/'additional_projections.json'))
    attached=defaultdict(lambda:{'units':set(),'locators':set(),'cases':set()})
    packet_checks=[]
    for row in results:
        cid=row['case_id']
        for mode in ('A12','S12'):
            base=load(harness.SCHEMA/f'packets/{cid}_{mode}.json')
            original=load(OUT/f'packets/{cid}_{mode}_original.json')
            assert base==original
            packet=load(OUT/f'packets/{cid}_{mode}_fact160.json')
            arm=row['arms'][mode+'_fact160'];decisions=arm['decisions']
            stripped=copy.deepcopy(packet)
            for doc in stripped['documents']:doc.pop('table_fact_units',None)
            assert stripped==base
            assert len(encoded(packet).encode('utf8'))==arm['packet_bytes']<=163840
            assert harness.digest(packet)==arm['packet_sha256']
            seen=set();count=0
            for doc,decision in zip(packet['documents'],decisions):
                uid=doc['chunk_id'];item=projections[uid];p=item['projection'];key=item['physical_key']
                assert decision['uid']==uid and decision['physical_key']==key
                wire=doc.get('table_fact_units')
                if key in seen:
                    assert not wire and decision['status']=='duplicate_table_first_owner_only'
                elif key:
                    seen.add(key)
                if not wire:continue
                assert p and decision['status']=='attached'
                assert {k:wire[k] for k in p['frame']}==p['frame']
                assert wire['source_id']==doc['source_id'] and wire['schema']==check.WIRE_SCHEMA
                locs=decision['cell_pool_locators']
                assert len(locs)==len(set(locs))==len(wire['cells'])
                assert [p['cells'][loc] for loc in locs]==wire['cells']
                saved={u['unit_id']:u for u in p['units']}
                accepted=[u for u in decision['units'] if u['status']=='attached']
                assert len(accepted)==len(wire['units'])==decision['unit_count']
                referenced=set()
                for i,(rec,u) in enumerate(zip(accepted,wire['units'])):
                    unit=saved[rec['unit_id']];r,c,v,ra,ca=u
                    assert rec['wire_unit_index']==i and [r,c]==unit['at']
                    assert locs[v]==unit['value'] and [locs[j] for j in ra]==unit['row_axes'] and [locs[j] for j in ca]==unit['column_axes']
                    referenced.update([v,*ra,*ca]);attached[uid]['units'].add(rec['unit_id'])
                assert referenced==set(range(len(locs)))
                attached[uid]['locators'].update(locs);attached[uid]['cases'].add(cid+'|'+mode)
                count+=len(wire['units'])
            assert count==arm['table_units']
            packet_checks.append({'case_id':cid,'arm':mode,'original_preserved':True,'bytes':arm['packet_bytes'],'units':count})
    metadata={}
    for path in sorted(harness.EXPORT.glob('*.jsonl.gz')):
        with gzip.open(path,'rt',encoding='utf8') as f:
            for line in f:
                row=json.loads(line);uid=row['metadata']['chunk_uid']
                if uid in attached:metadata[uid]=row['metadata']
    assert metadata.keys()==attached.keys()
    sys.path.insert(0,str(ROOT))
    from lxml import etree
    from src.processing.financial_parser import _sanitize_xml_like_text
    sources=load(harness.FACT/'source_checks.json');trees={};orders={}
    for receipt,source in sources.items():
        p=ROOT/source['path'];assert sha(p)==source['sha256']
        clean,_=_sanitize_xml_like_text(p.read_text(encoding='utf8'))
        parser=etree.XMLParser(no_network=True,resolve_entities=False,recover=False,huge_tree=True)
        trees[receipt]=etree.parse(BytesIO(clean.encode('utf8')),parser)
        assert not len(parser.error_log)
        orders[receipt]={n:i for i,n in enumerate(trees[receipt].getroot().iter())}
    cache={};checked=[];issues=[];physical_units=set();physical_cells=set();physical_contexts=set()
    for ordinal,(uid,a) in enumerate(sorted(attached.items()),1):
        m=metadata[uid];item=projections[uid];p=item['projection'];rec=item['receipt'];key=item['physical_key']
        obj=json.loads(m['table_object_json']);receipt=m['rcept_no'];tree=trees[receipt];source_sha=sources[receipt]['sha256'];frame=p['frame']
        before=len(issues)
        try:
            assert obj['source_document_sha256']==source_sha==frame['document_sha256']==rec['document_sha256']
            assert obj['table_id']==m['table_source_id']
            assert frame['table_locator']==obj['source_table_locator']==rec['table_locator']
            table=check.unique_node(tree,frame['table_locator'])
            if key not in cache:cache[key]=check.independent_geometry(tree,table)
            geom=cache[key]
            assert obj['row_count']==len(geom['grid']) and obj['column_count']==geom['width']
            prefix=[[check.literal(v) for v in r] for r in obj['header_rows']]
            assert prefix==geom['grid'][:len(prefix)]
            assert frame['declared_header_source_tr_indices']==geom['declared_raw']
            assert rec['raw_row_mapping']=={'kept_source_tr_indices':geom['kept'],'dropped_empty_source_tr_indices':geom['dropped']}
            contexts=[]
            for context in obj.get('source_contexts',[]):
                try:
                    valid,status=check.validate_context(context,tree,table,source_sha,orders[receipt])
                except (ValueError,TypeError,KeyError,IndexError,AttributeError):valid=None
                if valid is not None:contexts.append(valid)
            assert contexts==frame['literal_source_contexts']
            physical_contexts.update((key,harness.digest(c)) for c in contexts)
            units={u['unit_id']:u for u in p['units']};witness={u['unit_id']:u for u in rec['unit_witnesses']};rows={};roles=set()
            for unit_id in a['units']:
                unit=units[unit_id];w=witness[unit_id];vw=w['value_witness'];ri=vw['record_index']
                if ri not in rows:rows[ri]=check.row_contract(obj,geom,ri)
                record,row,positions,row_axes,prefix=rows[ri];col=vw['column'];index,cell,owner=positions[col]
                assert vw['kind']=='saved_row_cell' and vw['cell_record_index']==index and vw['saved_cell']==cell and vw['row_id']==record['row_id']
                assert unit['at']==w['at']==[row,col] and unit['value']==vw['cell_locator']==owner
                assert check.literal(cell['value_text'])==geom['grid'][row][col]
                assert [check.literal(v) for v in cell['column_headers']]==list(dict.fromkeys(r[col] for r in prefix if r[col]))
                assert unit['row_axes']==row_axes
                columns={c for loc in [owner,*row_axes] for rr,c in geom['cells'][loc]['expanded_coordinates'] if rr==row}
                column_axes=[]
                for pr in range(len(prefix)):
                    for pc in sorted(columns):
                        loc=geom['owners'][pr][pc]
                        if loc is not None and prefix[pr][pc] and loc not in column_axes:column_axes.append(loc)
                assert unit['column_axes']==column_axes
                expected_id=hashlib.sha256(f"{source_sha}\0{frame['table_locator']}\0{row}\0{col}\0{owner}".encode()).hexdigest()
                assert unit_id==expected_id
                roles.update([owner,*row_axes,*column_axes]);physical_units.add((key,row,col,owner))
            assert roles==a['locators']
            for loc in a['locators']:
                raw=geom['cells'][loc]
                assert p['cells'][loc]==[raw['source_tr_index'],raw['source_column_start'],raw['rowspan'],raw['colspan'],raw['value']]
                assert check.nearest_table(check.unique_node(tree,loc)) is table
                physical_cells.add((key,loc))
        except (AssertionError,ValueError,KeyError,IndexError,TypeError,AttributeError) as exc:
            issues.append({'uid':uid,'type':type(exc).__name__,'error':str(exc)})
        checked.append({'uid':uid,'physical_key':key,'units':len(a['units']),'cells':len(a['locators']),'issues':len(issues)-before})
        if ordinal%50==0:harness.beat('physical_audit',checked=ordinal,total=len(attached),issues=len(issues))
    result={'status':'PASS' if not issues else 'ISSUES','scope':'All154 enhanced packets; all delivered numeric units and dependencies; physical and saved-value provenance only.',
        'not_certified':['semantic subject/scope/period/unit assignment','completeness of original parser records','answer accuracy'],
        'input_hashes':{'results.json':sha(OUT/'results.json'),'additional_projections.json':sha(OUT/'additional_projections.json'),
            'frozen_projector':sha(harness.FACT/'projector.py'),'independent_geometry_helpers':sha(harness.BUDGET/'postrun_boundary_check.py')},
        'packet_checks':packet_checks,'unique_delivered_UIDs':len(attached),'unique_physical_tables':len(cache),
        'unique_physical_units':len(physical_units),'unique_physical_cells':len(physical_cells),'unique_table_context_spans':len(physical_contexts),
        'bindings':checked,'issues':issues,'external_model_API_calls':0,'projector_reexecuted':False}
    save('physical_audit.json',result)
    assert not issues,issues[:5]
    save('physical_entry.json',{'kind':'tool_receipt','step':'physical_packet_and_source_audit','status':'passed','command':'physical_audit.py',
        'exit_status':0,'retries_used':0,'input_sha256':{'results.json':sha(OUT/'results.json'),'physical_audit.py':sha(OUT/'physical_audit.py')},
        'output_sha256':sha(OUT/'physical_audit.json'),'gate_tokens':['154_PACKETS','SOURCE_BOUND_PHYSICAL_UNITS','SEMANTICS_NOT_CERTIFIED']})
    harness.beat('physical_audit_complete',tables=len(cache),units=len(physical_units),cells=len(physical_cells),issues=0)

if __name__=='__main__':main()
