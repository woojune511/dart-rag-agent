"""Read-only XML witness catalog; no parser/embedding/store mutation."""
from common import *
import re
from lxml import etree
def text(node): return re.sub(r'\s+',' ',''.join(node.itertext())).strip()
def main():
    from src.processing.financial_parser import _sanitize_xml_like_text
    receipt=[]
    for report in read(BASE/'acquisition.json')['reports']:
        raw=Path(report['source_file']).read_text('utf-8-sig')
        clean, sanitizer_changes=_sanitize_xml_like_text(raw)
        tree=etree.ElementTree(etree.fromstring(clean.encode('utf8'),etree.XMLParser(resolve_entities=False,no_network=True,recover=False,huge_tree=True)))
        blocks=[]
        for node in tree.iter():
            if not isinstance(node.tag,str): continue
            tag=node.tag.upper()
            if tag not in {'TITLE','SUBTITLE','P','TABLE'}: continue
            if any(isinstance(a.tag,str) and a.tag.upper()=='TABLE' for a in node.iterancestors()): continue
            literal=text(node)
            if not literal: continue
            b={'index':len(blocks),'xpath':tree.getpath(node),'kind':tag,'text':literal}
            if tag=='TABLE':
                b['rows']=[]
                for ri,tr in enumerate(node.xpath('.//TR')):
                    cells=[{'xpath':tree.getpath(c),'text':text(c),'rowspan':c.get('ROWSPAN','1'),'colspan':c.get('COLSPAN','1')} for c in tr if isinstance(c.tag,str) and c.tag.upper() in {'TD','TH','TE','TU'}]
                    if cells:b['rows'].append({'source_tr_index':ri,'cells':cells})
                b['preceding_blocks']=[{'xpath':p['xpath'],'kind':p['kind'],'text':p['text']} for p in blocks[-5:] if p['kind']!='TABLE']
            blocks.append(b)
        dest=BASE/'sources'/report['rcept_no']
        write(dest/'catalog.json',{'report':report,'tree_method':'Current sanitizer; strict XML; no external entities. Original file SHA remains authority. Whitespace normalized review text only.','blocks':blocks})
        with (dest/'review.txt').open('w',encoding='utf8') as f:
            for b in blocks:
                f.write(f"\n=== BLOCK {b['index']} {b['kind']} {b['xpath']} ===\n")
                if b['kind']=='TABLE':
                    for row in b['rows']: f.write(str(row['source_tr_index'])+': '+' | '.join(c['text'] for c in row['cells'])+'\n')
                else: f.write(b['text']+'\n')
        receipt.append({'rcept_no':report['rcept_no'],'blocks':len(blocks),'tables':sum(b['kind']=='TABLE' for b in blocks),'source_sha256':report['xml_sha256'],'catalog_sha256':sha(dest/'catalog.json'),'sanitizer_changes':sanitizer_changes})
    write(BASE/'catalog_receipt.json',{'status':'OFFLINE_WITNESS_CATALOG_CREATED','reports':receipt,'model_api_calls':0})
    print(json.dumps(receipt,ensure_ascii=False))
if __name__=='__main__':
    with offline(): main()
