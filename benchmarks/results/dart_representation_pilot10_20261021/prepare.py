"""Offline corpus construction; never alters app stores or source code."""
from common import *
import gzip, threading, time, logging
os.environ['TIKTOKEN_CACHE_DIR'] = str(ROOT/'benchmarks/results/full77_v12_final_20261018/tokenizer_cache')

def main():
    from lxml import etree
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from src.processing.financial_parser import FinancialParser
    from src.ops.benchmark_runner import _build_structural_selective_prefixed_text, _selective_reason_v2
    from src.config.simple_rag import SOURCE_CONTEXT_FIELDS
    import tiktoken
    encoder = tiktoken.get_encoding('cl100k_base')
    stats=[]
    for r in load(BASE/'acquisition.json')['reports']:
        rid=r['rcept_no']; source=Path(r['source_file'])
        assert sha(source)==r['xml_sha256']
        meta={k:r[k] for k in ('company','year','rcept_no')};meta['report_type']='사업보고서'
        print('PREPARE',r['company'],flush=True)
        tree=etree.parse(str(source),etree.HTMLParser(recover=True,remove_comments=True,no_network=True))
        values=tree.xpath('//text()[not(ancestor::script) and not(ancestor::style) and not(ancestor::noscript)]')
        flat='\n'.join(s for value in values if (s:=' '.join(str(value).split())))
        assert len(flat)>100000 and '매출' in flat and '연결' in flat
        with (BASE/'sources'/rid/'generic_text.txt').open('x',encoding='utf-8') as f:f.write(flat)
        splitter=RecursiveCharacterTextSplitter(chunk_size=2500,chunk_overlap=320,separators=['\n\n','\n',' ',''],length_function=len)
        generic=[(text,{**meta,'chunk_uid':f'{rid}:generic:{i}','chunk_id':i}) for i,text in enumerate(splitter.split_text(flat))]
        start=time.monotonic()
        chunks=FinancialParser(chunk_size=2500,chunk_overlap=320,section_parse_budget_sec=0).process_document(str(source),meta)
        assert chunks
        dart=[(_build_structural_selective_prefixed_text(c.metadata,c.content,selected_reason=_selective_reason_v2(c)),c.metadata) for c in chunks]
        for arm,rows in [('generic',generic),('dart',dart)]:
            exported=[]
            for text,m in rows:
                n=len(encoder.encode(text,disallowed_special=()))
                assert 0<n<=8192, f'Embedding chunk too long: {arm} {m["chunk_uid"]} {n}'
                exported.append({'id':m['chunk_uid'],'text':text,'metadata':{k:v for k,v in m.items() if k in SOURCE_CONTEXT_FIELDS or k in ('chunk_uid','chunk_id')},'tokens':n})
            path=BASE/f'{arm}_{rid}.jsonl.gz'
            with gzip.open(path,'xt',encoding='utf-8',newline='\n') as f:
                for row in exported:f.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
            stats.append({'arm':arm,'company':r['company'],'rcept_no':rid,'chunks':len(exported),'tokens':sum(x['tokens'] for x in exported),'max_chunk_tokens':max(x['tokens'] for x in exported),'path':str(path),'sha256':sha(path)})
        print('PREPARED',r['company'],len(generic),len(dart),round(time.monotonic()-start,1),flush=True)
    write(BASE/'corpus_manifest.json',{'created_at':now(),'corpora':stats,'embedding_tokens':sum(x['tokens'] for x in stats),'usd_at_013_per_million':sum(x['tokens'] for x in stats)*.13/1e6})

if __name__=='__main__':
    halt=threading.Event()
    def heartbeat():
        while not halt.wait(15):print('PREPARATION_HEARTBEAT',now(),flush=True)
    threading.Thread(target=heartbeat,daemon=True).start()
    try:
        with offline():main()
    finally:halt.set()
