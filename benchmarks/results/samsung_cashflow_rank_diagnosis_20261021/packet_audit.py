"""Offline packet-size and source-preservation checks; no answer generation."""
from diagnose import *
from urllib.parse import quote
import tiktoken
from lxml import etree

def main():
    verify()
    design=load(BASE/'design.json');w=load(BASE/'source_witness.json')
    group=etree.fromstring(w['source_group_xml'].encode())
    cells=[' '.join(''.join(e.itertext()).split()) for e in group.findall('TABLE')[1].iter() if e.tag in ('TH','TD','TE')]
    canon=lambda s:re.sub(r'[\s|]','',s)
    generic_cells=w['generic_text'].split(w['caption'],1)[1].strip().split('\n3. 연결재무제표 주석',1)[0]
    assert canon(w['raw_body'])==canon(''.join(cells))==canon(generic_cells)
    checks={'cell_content_equal_after_whitespace_and_pipe_normalization':True,
            'number_signs_commas_and_parentheses_preserved':True,
            'cashflow_title_in_rich_table_source_contexts':any('연결 현금흐름표' in x['source_text'] for x in json.loads(w['target_metadata']['table_object_json'])['source_contexts']),
            'cashflow_title_absent_from_search_text':'연결 현금흐름표' not in w['prefix']+w['raw_body']}
    assert all(checks.values())
    base=load(BASE/'baseline.json');analyses=load(BASE/'offline_analysis.json')['results'];encoder=tiktoken.get_encoding('cl100k_base')
    originals={a:rows(OLD/f'{a}_{RID}.jsonl.gz') for a in ('dart','generic')}
    observations=[]
    for name,arm,target,result in [
        ('dart','dart',TID,base['dart']),('generic','generic',GID,base['generic']),
        ('bm25_dart_caption_restored','dart',TID,analyses['bm25_dart_caption_restored']),
        ('bm25_all_no_keywords','dart',TID,analyses['bm25_all_no_keywords']),
        ('bm25_generic_caption_removed','generic',GID,analyses['bm25_generic_caption_removed'])]:
        ds={x['id']:dict(x) for x in originals[arm]}
        if name=='bm25_all_no_keywords':
            for x in rows(BASE/'no_keywords.jsonl.gz'):ds[x['id']]['text']=x['text']
        elif name.startswith('bm25_'):
            edit=next(x for x in design['counterfactuals'] if 'bm25_'+x['name']==name)
            ds[edit['target']]['text']=edit['text']
        packet={'query':design['question']['query'],'report_scope':{'rcept_no':RID},'documents':[]};omitted=[]
        for rank in result['rrf_candidates'][:12]:
            row=ds[rank['id']];uid=row['id']
            item={'source_id':quote(RID,safe='')+':'+quote(uid,safe=''),'document_id':RID,'chunk_id':uid,'text':row['text'],
                  'context':{k:v for k,v in row['metadata'].items() if k not in ('chunk_uid','chunk_id')}}
            proposal={**packet,'documents':packet['documents']+[item]}
            nt=len(encoder.encode(original.enc(original.body(proposal)).decode(),disallowed_special=()))
            if len(original.enc(proposal))>65536 or nt>12000:
                omitted.append(uid);continue
            packet=proposal
        if name in ('dart','generic'):
            assert packet==load(OLD/'packets'/f'02_capex_{name}.json')
        write(BASE/'packet_replays'/f'{name}.json',packet)
        observations.append({'name':name,'target_in_packet':any(x['chunk_id']==target for x in packet['documents']),
              'selected':[x['chunk_id'] for x in packet['documents']],'omitted':omitted,
              'bytes':len(original.enc(packet)),'request_proxy_tokens':len(encoder.encode(original.enc(original.body(packet)).decode(),disallowed_special=()))})
    write(BASE/'packet_audit.json',{'source_checks':checks,'replays':observations,'no_answer_calls':True,
           'note':'Counterfactual packet sizes only; BM25-only selection with original dense vectors fixed, modified source text included in simulated packet.'})
    for r in observations:print(r['name'],'target_in_packet',r['target_in_packet'],'docs',len(r['selected']),'tokens',r['request_proxy_tokens'])

if __name__=='__main__':
    with offline():main()
