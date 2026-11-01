"""Read only assigned masked batch; no arm map or outcome access."""
import json,sys
from pathlib import Path
folder=Path(sys.argv[1]).resolve()
load=lambda p:json.loads(p.read_text('utf8'))
def show(x):print(json.dumps(x,ensure_ascii=False,indent=2))
cases=load(folder/'rubric.json')['cases'];items=load(folder/'items.json')
if len(sys.argv)==2:show([{'case_id':c['case_id'],'question':c['question'],'kind':c['kind']} for c in cases])
elif sys.argv[2].startswith('H'):
    cid=sys.argv[2];show({'criterion':next(c for c in cases if c['case_id']==cid),'answers':[x for x in items if x['case_id']==cid]})
else:
    rid=sys.argv[2];item=next(x for x in items if x['review_id']==rid);packet=load(folder/item['packet_path'])
    if len(sys.argv)==3:
        show({'query':packet['query'],'documents':[{'index':i,'source_id':d['source_id'],'cited':d['source_id'] in (item['answer'] or {}).get('cited_source_ids',[]),'context':d['context'],'text':d['text'],
          'fact_units_count':len(d.get('table_fact_units',{}).get('units',[])),'fact_frame':{k:v for k,v in d.get('table_fact_units',{}).items() if k not in ('cells','units')}} for i,d in enumerate(packet['documents'])]})
    else:
        doc=packet['documents'][int(sys.argv[3])]
        if len(sys.argv)==4:show(doc)
        else:
            term=sys.argv[4];wire=doc.get('table_fact_units',{});cells=wire.get('cells',[])
            matching=[]
            for i,u in enumerate(wire.get('units',[])):
                idx=[u[2],*u[3],*u[4]]
                if any(term in str(cells[k][4]) for k in idx):
                    matching.append({'unit_index':i,'at':u[:2],'value':cells[u[2]],'row_axes':[cells[k] for k in u[3]],'column_axes':[cells[k] for k in u[4]]})
            show({'source_id':doc['source_id'],'text':doc['text'],'context':doc['context'],'frame':{k:v for k,v in wire.items() if k not in ('cells','units')},'matching_units':matching})
