"""Display one assigned masked case with its frozen criterion; no arm lookup."""
from pathlib import Path
import json
import sys

batch=Path(sys.argv[1]).resolve()
cases=json.loads((batch/'rubric.json').read_text('utf-8'))['cases']
items=json.loads((batch/'items.json').read_text('utf-8'))
if len(sys.argv)==2:
    print(json.dumps([{'case_id':c['case_id'],'group':c['group'],'question':c['question'],
                       'review_ids':[x['review_id'] for x in items if x['case_id']==c['case_id']]} for c in cases],ensure_ascii=False,indent=2))
else:
    cid=sys.argv[2]
    criterion=next(c for c in cases if c['case_id']==cid)
    answers=[x for x in items if x['case_id']==cid]
    print(json.dumps({'criterion':criterion,'answers':answers},ensure_ascii=False,indent=2))
