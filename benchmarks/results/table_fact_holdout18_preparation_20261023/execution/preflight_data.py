from common_exec import *
import copy, socket
from unittest.mock import patch
from src.storage.structure_graph import empty_structure_graph,update_structure_graph
from src.storage.metadata_payloads import compact_node_for_storage,metadata_with_table_payload
def denied(*a,**k):raise Stop('Offline contract audit')
socket.create_connection=socket.getaddrinfo=socket.socket.connect=socket.socket.connect_ex=denied
rows=corpus();graph=update_structure_graph(empty_structure_graph(),[r['text'] for r in rows],[r['metadata'] for r in rows],lambda m:m['chunk_uid'])
payloads={};table_keys=[]
for r in rows:
    node=compact_node_for_storage(graph['nodes'][r['uid']],payloads)
    hydrated=metadata_with_table_payload(node['metadata'],payloads)
    if 'table_payload_id' not in r['metadata']:hydrated.pop('table_payload_id',None)
    need(node['text']==r['text'] and hydrated==r['metadata'],'Full corpus hydration mismatch '+r['uid'])
    obj=json.loads(r['metadata'].get('table_object_json') or '{}')
    if obj:table_keys.append(obj.get('source_document_sha256','')+'|'+obj.get('source_table_locator',''))
from offline_stage import CachedEmbeddings,packet_from_native
from src.storage.vector_store import VectorStoreManager
emb=CachedEmbeddings({'fixture':[1.0]+[0.0]*3071})
with patch('src.storage.vector_store.create_embeddings',lambda **kw:emb):
    vsm=VectorStoreManager(persist_directory=str(OUT/'smoke_store_hydration'),collection_name='holdout18_v12_20261023',allow_query_embedding_fallback=False)
hits=vsm.search('fixture',k=1,k_rrf=60,where_filter={'rcept_no':rows[0]['metadata']['rcept_no']})
need(len(hits)==1 and emb.used==['fixture'],'Native cached-vector search')
from lxml import etree
from src.processing.financial_parser import _sanitize_xml_like_text
projector=module(ROOT/'benchmarks/results/table_fact_units_offline_20261023/projector.py','preflight_projector')
assembler=module(ROOT/'benchmarks/results/table_fact_units_offline_20261023/run.py','preflight_assembler');assembler.CAP=163840
r=next(r for r in rows if r['metadata'].get('table_object_json'))
p=PREP/'sources'/r['metadata']['rcept_no']/'original.xml';clean,_=_sanitize_xml_like_text(p.read_text('utf8'))
tree=etree.ElementTree(etree.fromstring(clean.encode('utf8'),etree.XMLParser(recover=False,no_network=True,resolve_entities=False,huge_tree=True)))
proj,receipt=projector.build_units(r['metadata'],tree,sha(p))
obj=json.loads(r['metadata']['table_object_json']);key=obj['source_document_sha256']+'|'+obj['source_table_locator']
packet={'query':'fixture','report_scope':{'rcept_no':r['metadata']['rcept_no']},'documents':[{'chunk_id':r['uid'],'source_id':'fixture','text':r['text'],'context':{}}]}
changed,decisions=assembler.project_packet(packet,{r['uid']:{'physical_key':key,'projection':proj,'receipt':receipt}})
stripped=copy.deepcopy(changed)
for d in stripped['documents']:d.pop('table_fact_units',None)
need(stripped==packet and len(enc(changed))<=163840,'Frozen projector packet parity')
put(OUT/'data_contract_validation.json',{'status':'PASS','full_corpus_exact_hydration':len(rows),'unique_physical_tables':len(set(table_keys)),
  'native_cached_vector_query':True,'physical_key_matches_frozen':True,'native_fact_assembly_parity':True,
  'sample_projection_status':receipt['status'],'external_calls':0,'preservation':frozen()})
print('DATA CONTRACT PASS: all3768 hydration, native cached query, frozen fact assembly;0 calls',flush=True)
