"""Read sealed outputs and export review dossiers; never judges or calls a provider."""
from common import *
import re

def main():
    assert (BASE/'execution_complete.json').exists()
    for seal in ('raw_seal.json','packets_seal.json'):
        for p,digest in load(BASE/seal).items():assert sha(p)==digest
    results=[]
    for q in load(BASE/'rubric.json')['questions']:
        dossier=['# '+q['id'],q['query'],'Gold/rubric: '+json.dumps(q,ensure_ascii=False)]
        for arm in ('generic','dart'):
            packet=load(BASE/'packets'/f'{q["id"]}_{arm}.json')
            alltext='\n'.join(x['text']+'\n'+json.dumps(x['context'],ensure_ascii=False) for x in packet['documents'])
            # Literal presence is diagnostic only, never a correctness/faithfulness verdict.
            presence={k:f'{v:,}' in alltext or str(v) in alltext for k,v in q.get('gold',{}).items() if k.endswith('_krw')}
            dossier+=['\n## '+arm,'Literal exact-won presence (not semantic coverage): '+json.dumps(presence)]
            cited=set()
            for repeat in (1,2):
                cid=f'{q["id"]}_{arm}_r{repeat}';answer=load(BASE/'live'/cid/'answer.value.json')
                cited.update(answer['cited_source_ids'])
                dossier+=['\n### Repeat '+str(repeat),json.dumps(answer,ensure_ascii=False,indent=2)]
                results.append({'id':q['id'],'arm':arm,'repeat':repeat,'type':q['type'],**answer,'literal_gold_presence':presence})
            dossier+=['\n### All supplied evidence (cited marked)']
            for d in packet['documents']:
                dossier+=['\n'+('CITED ' if d['source_id'] in cited else 'UNCITED ')+d['source_id'],json.dumps(d['context'],ensure_ascii=False),d['text']]
        path=BASE/'review'/f'{q["id"]}.txt';path.parent.mkdir(exist_ok=True)
        with path.open('x',encoding='utf-8',newline='\n') as f:f.write('\n'.join(dossier))
    write(BASE/'review'/'answers.json',results)
    print('Exported 10 evidence dossiers and 40 answers from sealed outputs; no automatic semantic grades.')

if __name__=='__main__':main()
