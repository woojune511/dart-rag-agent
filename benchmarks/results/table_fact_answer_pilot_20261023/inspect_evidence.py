"""Read-only display of exact packet text and fact-cell references for local reviewers."""
import json
from pathlib import Path
import sys

p=json.loads(Path(sys.argv[1]).read_text('utf-8'))
needles=[s.casefold() for s in sys.argv[2:]]
def matches(s):return not needles or any(n in s.casefold() for n in needles)
for d in p['documents']:
    f=d.get('table_fact_units')
    texts=[]
    t=d['text']
    for n in needles:
        pos=t.casefold().find(n)
        if pos>=0:texts.append(t[max(0,pos-200):pos+len(n)+350])
    if not needles:texts=[t]
    units=[]
    if f:
        cells=f['cells']; declared=f['declared_header_source_tr_indices']
        for i,u in enumerate(f['units']):
            row=[cells[j][-1] for j in u[3]]
            col=[cells[j][-1] for j in u[4]]
            value=cells[u[2]][-1]
            if matches(' | '.join([*row,*col,value])):
                units.append({'index':i,'at':u[:2],'value':value,'row_literals':row,'column_prefix_literals':col,
                    'prefix_has_actual_header':[cells[j][0] in declared for j in u[4]],'pool_indices':u[2:]})
    if texts or units:
        print(json.dumps({'source_id':d['source_id'],'text_excerpts':texts,'context':d['context'],
            'fact_contexts':f['literal_source_contexts'] if f else [],
            'matching_units':units[:75],'matched_unit_count':len(units),
            'warning':'Column prefix literal need not be semantic header. See raw packet for full text and coordinates.'},ensure_ascii=False,indent=2))
