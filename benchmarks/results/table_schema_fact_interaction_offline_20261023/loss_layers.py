"""Postrun mechanical loss attribution; never a required-fact or answer score."""
from collections import Counter
import run

rows=run.load(run.OUT/'results.json')
out=[];totals=Counter()
for row in rows:
    first={}
    for d in row['arms']['S12_fact160']['decisions']:
        key=d['physical_key']
        if key and key not in first:first[key]=d
    counts=Counter();losses=[]
    for key in row['physical_unit_changes']['lost']:
        table,at=key.rsplit('|',1)
        decision=first.get(table)
        if decision is None:
            layer='physical_table_absent_from_actual_S12_documents'
        else:
            address=[int(v) for v in at.split(':')]
            u=next((u for u in decision.get('units',[]) if u['at']==address),None)
            if u is not None:
                assert u['status']!='attached',key
                layer=u['status']
            else:
                layer='not_admitted_by_S12_first_owner_projection'
        counts[layer]+=1
        losses.append({'physical_unit':key,'layer':layer,'first_owner':decision['uid'] if decision else None})
    totals.update(counts)
    out.append({'case_id':row['case_id'],'counts':dict(counts),'lost_unit_events':losses})
run.save('loss_layers.json',{'status':'COMPLETED_MECHANICAL_ATTRIBUTION','interpretation':'Lost numeric-cell delivery events, not mandatory evidence failures. Absent actual S12 table can include top12 selection or pre-existing original whole-source byte omission; these are not separated here.',
    'input_sha256':run.sha(run.OUT/'results.json'),'total_lost_unit_events':sum(totals.values()),'counts':dict(totals),'cases':out})
print(dict(totals))
