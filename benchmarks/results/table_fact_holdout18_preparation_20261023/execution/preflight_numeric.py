from common_exec import *
import copy,socket
def denied(*a,**k):raise Stop('Offline contract audit')
socket.create_connection=socket.getaddrinfo=socket.socket.connect=socket.socket.connect_ex=denied
from lxml import etree
from src.processing.financial_parser import _sanitize_xml_like_text
projector=module(ROOT/'benchmarks/results/table_fact_units_offline_20261023/projector.py','numeric_projector')
assembler=module(ROOT/'benchmarks/results/table_fact_units_offline_20261023/run.py','numeric_assembler');assembler.CAP=163840
trees={};verified=[]
for r in corpus():
    rid=r['metadata']['rcept_no'];obj=json.loads(r['metadata'].get('table_object_json') or '{}')
    if not obj or any(x['receipt']==rid for x in verified):continue
    p=PREP/'sources'/rid/'original.xml'
    if rid not in trees:
        clean,_=_sanitize_xml_like_text(p.read_text('utf8'))
        trees[rid]=etree.ElementTree(etree.fromstring(clean.encode('utf8'),etree.XMLParser(recover=False,no_network=True,resolve_entities=False,huge_tree=True)))
    proj,receipt=projector.build_units(r['metadata'],trees[rid],sha(p))
    if not proj or not proj['units']:continue
    key=obj['source_document_sha256']+'|'+obj['source_table_locator']
    doc={'chunk_id':r['uid'],'source_id':'fixture','text':r['text'],'context':{}}
    packet={'query':'fixture','report_scope':{'rcept_no':rid},'documents':[doc]}
    changed,decisions=assembler.project_packet(packet,{r['uid']:{'physical_key':key,'projection':proj,'receipt':receipt}})
    need(changed['documents'][0]['table_fact_units']['units'],'No attached numeric units')
    stripped=copy.deepcopy(changed)
    for d in stripped['documents']:d.pop('table_fact_units',None)
    need(stripped==packet and len(enc(changed))<=163840,'Numeric packet parity')
    verified.append({'receipt':rid,'sample_uid':r['uid'],'verified_units':len(proj['units']),'attached_units':len(changed['documents'][0]['table_fact_units']['units'])})
    if len(verified)==3:break
need(len(verified)==3,'Numeric projection coverage')
put(OUT/'numeric_contract_validation.json',{'status':'PASS','per_report':verified,'external_calls':0,'source_rule':'First numeric table per report, no question-aware selection'})
print('NUMERIC CONTRACT PASS',verified,flush=True)
