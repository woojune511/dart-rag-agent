"""Bounded prior project-file receipt and source ownership audit, not training-data audit."""
from common import *
import re, collections
def main():
    reports=read(BASE/'acquisition.json')['reports'];receipts={x['rcept_no'] for x in reports}
    roots=['benchmarks','docs','data/reports']
    archive=Path('D:/CodexArtifacts/dart-rag-agent')
    if archive.is_dir():roots.append(str(archive))
    command=['rg','--files','--hidden','--no-ignore',*sum((['-g',g] for g in ['*.md','*.json','*.jsonl','*.yaml','*.yml','*.html','*.xml']),[]),*roots]
    names=subprocess.check_output(command,cwd=ROOT,text=True,encoding='utf8').splitlines()
    # Every filename is audited. Full receipt scan covers all selected textual files, without a size skip.
    files=[];hits=[];raw_sources=[];owners=set();old_questions=set()
    def walk(v):
        if isinstance(v,dict):
            if isinstance(v.get('company'),str) and isinstance(v.get('rcept_no'),str):owners.add((v['company'],v['rcept_no']))
            for k,x in v.items():
                if k in ('question','query','user_question') and isinstance(x,str) and len(x)>8: old_questions.add(x)
                elif isinstance(x,(dict,list)):walk(x)
        elif isinstance(v,list):
            for x in v:walk(x)
    for n in sorted(set(names)):
        p=Path(n);p=p if p.is_absolute() else ROOT/p
        if p.is_relative_to(BASE):continue
        # receipts are ASCII; scan chunks with overlap even for very large results
        h=hashlib.sha256();found=set();tail=b''
        with p.open('rb') as f:
            for b in iter(lambda:f.read(4*1024*1024),b''):
                h.update(b);window=tail+b
                found.update(r for r in receipts if r.encode() in window)
                tail=window[-20:]
        entry={'path':str(p),'bytes':p.stat().st_size,'sha256':h.hexdigest()};files.append(entry)
        if found:hits.append({**entry,'receipt_matches':sorted(found)})
        if p.suffix in ('.xml','.html') and re.search(r'20\d{12}',str(p)) and p.stat().st_size>400000:raw_sources.append(entry)
        # extract questions and explicit source-owner objects from evaluation design artifacts.
        if p.suffix=='.json' and (any(x in p.name.lower() for x in ('question','panel','manifest','dataset','selection','protocol','preparation','gold')) or 'datasets' in p.parts):
            try:walk(json.loads(p.read_text('utf-8-sig')))
            except (UnicodeError,json.JSONDecodeError):pass
    duplicates=[{'new_receipt':r['rcept_no'],'prior':x['path']} for r in reports for x in raw_sources if r['xml_sha256']==x['sha256']]
    overlap_owners=[x for x in sorted(owners) if x[1] in receipts]
    write(BASE/'prior_questions.json',sorted(old_questions))
    write(BASE/'exposure_audit.json',{'at':now(),'roots':roots,'files':files,'files_scanned':len(files),'receipt_matches':hits,
       'prior_source_sha_duplicates':duplicates,'new_receipt_owner_matches':overlap_owners,'source_owners':sorted(owners),
       'old_questions':len(old_questions),'method':'All receipt strings scanned across selected text extensions in project and named artifact archive; no byte-size skip. Structured question/owner extraction is bounded to named design artifacts. No Git-history, deleted-file, external-history, model-training or semantic-independence proof.',
       'status':'NO_RECORDED_RECEIPT_OR_SOURCE_OVERLAP' if not(hits or duplicates or overlap_owners) else 'REVIEW_OVERLAP'})
    print(json.dumps({'files':len(files),'receipt_matches':hits,'source_duplicates':duplicates,'owner_matches':overlap_owners,'old_questions':len(old_questions)},ensure_ascii=False))
if __name__=='__main__':
    with offline():main()
