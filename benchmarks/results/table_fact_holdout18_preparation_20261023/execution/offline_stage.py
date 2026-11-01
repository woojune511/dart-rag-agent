"""Provider-free store/retrieval and native packet capture, in a separate process."""
from common_exec import *
import copy, math, socket
from unittest.mock import patch

def denied(*a,**k): raise Stop('Offline stage networking forbidden')
socket.create_connection=socket.getaddrinfo=socket.socket.connect=socket.socket.connect_ex=denied
os.environ['ANONYMIZED_TELEMETRY']='False'

def build_store(rows,vectors,path):
    import chromadb
    from chromadb.config import Settings
    from src.storage.structure_graph import empty_structure_graph,update_structure_graph
    from src.storage.graph_persistence import persist_structure_graph
    from src.storage.metadata_payloads import compact_node_for_storage, metadata_for_chroma
    from src.storage.store_manifest import StoreManifestV1,write_store_manifest,assess_store_readiness
    from src.ops.build_parser_store_successor import _vector, _check_vector_rows, _read_vectors
    from src.storage.vector_store import DEFAULT_CHROMA_HNSW_BATCH_SIZE,DEFAULT_CHROMA_HNSW_SYNC_THRESHOLD
    need(not path.exists(),'Store must be new');path.mkdir()
    manifest=StoreManifestV1.from_projection(load(PREP/'protocol.json')['retrieval']['manifest'])
    graph=update_structure_graph(empty_structure_graph(),[r['text'] for r in rows],[r['metadata'] for r in rows],lambda m:m['chunk_uid'])
    graph,payloads=persist_structure_graph(path/'document_structure_graph.json',path/'table_payloads.json',graph,
      compact_node_for_storage=compact_node_for_storage,existing_payloads={})
    # Parent expansion is not part of this frozen search/delivery path.
    put(path/'parents.json',{})
    client=chromadb.PersistentClient(path=str(path),settings=Settings(anonymized_telemetry=False))
    collection=client.create_collection(manifest.collection_name,embedding_function=None,
      metadata={'hnsw:batch_size':DEFAULT_CHROMA_HNSW_BATCH_SIZE,'hnsw:sync_threshold':DEFAULT_CHROMA_HNSW_SYNC_THRESHOLD})
    records={r['uid']:{'text':r['text'],'metadata':metadata_for_chroma(graph['nodes'][r['uid']]['metadata']),
      'embedding':_vector(vectors[r['text_sha256']],3072)} for r in rows}
    need(len(records)==len(rows),'Duplicate UID')
    ids=list(records)
    for i in range(0,len(ids),128):
        group=ids[i:i+128]
        collection.add(ids=group,documents=[records[k]['text'] for k in group],metadatas=[records[k]['metadata'] for k in group],embeddings=[records[k]['embedding'] for k in group])
    _check_vector_rows(_read_vectors(collection),records,3072)
    write_store_manifest(path,manifest)
    readiness=assess_store_readiness(path,expected=manifest)
    need(readiness.ready and not readiness.degraded and readiness.status=='compatible','New store readiness')
    result={'status':readiness.status,'reason':readiness.reason,'vectors':len(records),'graph_nodes':len(graph['nodes']),
      'table_payloads':len(payloads),'stored_vector_text_metadata_exact':True,'hnsw_space':collection.configuration['hnsw']['space'],
      'parent_expansion':False,'active_store_opened':False}
    need(result['hnsw_space']=='l2','Default index distance drift')
    return result

class CachedEmbeddings:
    def __init__(self,lookup): self.lookup=lookup;self.used=[]
    def embed_query(self,text):
        need(text in self.lookup and text not in self.used,'Unexpected or duplicate embedding query')
        self.used.append(text);return self.lookup[text]
    def embed_documents(self,texts): raise Stop('Unplanned embedding document call')

def packet_from_native(question,hits):
    from src.agent.simple_rag import SimpleRagAgent
    class Store:
        last_search_telemetry={'retrieval_mode':'hybrid'}
        _caption_links={}
        def search(self,query,**kw):
            need(query==question['question'] and kw['k']==12 and kw['where_filter']==question['report_scope'],'Native packet inputs')
            return hits
    class Recorder:
        packet=None
        def with_structured_output(self,schema):return self
        def invoke(self,messages):
            self.packet=json.loads(messages[1][1]);return {'answer':'offline packet capture','abstained':True,'cited_source_ids':[]}
    recorder=Recorder()
    with patch.object(SimpleRagAgent,'_build_llm_routes',lambda self:{'default':recorder}):
        agent=SimpleRagAgent(Store(),k=12,max_context_bytes=65536)
        result=agent.run(question['question'],report_scope=question['report_scope'],include_debug_bundle=True,include_review_trace=True)
    need(recorder.packet is not None,'No model-visible sources; frozen 72-answer schedule cannot proceed')
    return recorder.packet,result.to_projection()

def row(pair):
    d,s=pair;return {'text':d.page_content,'metadata':d.metadata,'score':float(s)}

def real():
    frozen()
    rows=corpus();byuid={r['uid']:r for r in rows}
    import numpy as np
    for name,h in load(OUT/'live/vector_receipts.json')['files'].items():
        need(sha(OUT/'live'/name)==h,'Cached vector receipt drift '+name)
    vector_file=load(OUT/'live/vector_manifest.json')
    need(sha(OUT/'live/document_vectors.npy')==vector_file['array_sha256'],'Document vector array drift')
    arr=np.load(OUT/'live/document_vectors.npy',allow_pickle=False)
    vectors={h:arr[i].tolist() for i,h in enumerate(vector_file['text_sha256'])}
    checks=build_store(rows,vectors,OUT/'store')
    from src.storage.vector_store import VectorStoreManager
    from src.storage import search_merge
    qs=load(PREP/'questions.json');qvec=load(OUT/'live/query_vectors.json')
    need(set(qvec)=={q['case_id'] for q in qs},'Cached query coverage')
    emb=CachedEmbeddings({q['question']:qvec[q['case_id']] for q in qs})
    with patch('src.storage.vector_store.create_embeddings',lambda **kw:emb):
        vsm=VectorStoreManager(persist_directory=str(OUT/'store'),collection_name=load(PREP/'protocol.json')['execution_collection'],
          embedding_provider='openai',embedding_model_name='text-embedding-3-large',allow_query_embedding_fallback=False,
          force_bm25_only=False,experimental_lexical_policy_id=None,experimental_caption_links_path=None)
    integrity=vsm.validate_source_integrity();need(integrity['ready'],'Source integrity')
    checks['source_integrity']=integrity;need(len(vsm.bm25_docs)==3768,'BM25 corpus size')
    # Verify hydrated source text/metadata against every frozen row, not just IDs.
    for uid,r in byuid.items():
        node=vsm._structure_graph['nodes'][uid]
        hydrated=vsm._metadata_with_table_payload(node['metadata'])
        if 'table_payload_id' not in r['metadata']:hydrated.pop('table_payload_id',None)
        need(node['text']==r['text'] and hydrated==r['metadata'],'Hydrated source drift '+uid)
    put(OUT/'store_checks.json',checks)
    merge=search_merge.merge_rrf_results;captured={}
    def observe(dense,bm25,*,k,k_rrf):
        need(k==8 and k_rrf==60 and len(dense)==16 and len(bm25)<=24,'Candidate parameters')
        selected=merge(dense,bm25,k=12,k_rrf=60)
        captured.update(dense=[row(x) for x in dense],bm25=[row(x) for x in bm25],rrf=[row(x) for x in selected],hits=selected)
        return merge(dense,bm25,k=k,k_rrf=k_rrf)
    packets={}
    with patch.object(search_merge,'merge_rrf_results',observe):
        for q in qs:
            captured.clear();vsm.search(q['question'],k=8,k_rrf=60,where_filter=q['report_scope'])
            need(len(captured['rrf'])==12,'Final selected cardinality')
            packet,projection=packet_from_native(q,captured.pop('hits'))
            captured.update(case_id=q['case_id'],query=q['question'],scope=q['report_scope'],telemetry=vsm.last_search_telemetry)
            put(OUT/'retrieval'/f'{q["case_id"]}.json',captured)
            put(OUT/'packets'/f'{q["case_id"]}_A.json',packet)
            put(OUT/'native_capture'/f'{q["case_id"]}.json',projection)
            packets[q['case_id']]=packet
    need(len(emb.used)==18,'One saved query embedding consumed per question')
    from lxml import etree
    from src.processing.financial_parser import _sanitize_xml_like_text
    projector=module(ROOT/'benchmarks/results/table_fact_units_offline_20261023/projector.py','frozen_fact_projector')
    assembler=module(ROOT/'benchmarks/results/table_fact_units_offline_20261023/run.py','frozen_fact_assembler')
    assembler.CAP=163840
    trees={};hashes={}
    for q in qs:
        rid=q['receipt']
        if rid in trees:continue
        p=PREP/'sources'/rid/'original.xml';hashes[rid]=sha(p)
        clean,edits=_sanitize_xml_like_text(p.read_text('utf8'))
        trees[rid]=etree.ElementTree(etree.fromstring(clean.encode('utf8'),etree.XMLParser(recover=False,no_network=True,resolve_entities=False,huge_tree=True)))
    projections={}
    for packet in packets.values():
        for doc in packet['documents']:
            uid=doc['chunk_id']
            if uid in projections:continue
            meta=byuid[uid]['metadata'];rid=meta['rcept_no']
            projection,receipt=projector.build_units(meta,trees[rid],hashes[rid])
            key=None
            if meta.get('table_object_json'):
                obj=json.loads(meta['table_object_json'])
                key=obj.get('source_document_sha256','')+'|'+obj.get('source_table_locator','')
            projections[uid]={'physical_key':key,'projection':projection,'receipt':receipt}
    # physical_key uses the exact frozen helper's report-hash/table locator rule.
    entries=[];parity=[]
    for q in qs:
        cid=q['case_id'];a=packets[cid];c,decisions=assembler.project_packet(a,projections)
        stripped=copy.deepcopy(c)
        for d in stripped['documents']:d.pop('table_fact_units',None)
        need(stripped==a,'A/C original packet drift')
        put(OUT/'packets'/f'{cid}_C.json',c);put(OUT/'projection_decisions'/f'{cid}.json',decisions)
        for arm,packet in [('A',a),('C',c)]:
            need(len(enc(packet))<=(65536 if arm=='A' else 163840),'Packet cap')
            body=copy.deepcopy(load(PREP/'protocol.json')['fixed_generation']);body['input'][1]['content']=enc(packet).decode('utf8')
            bound=len(enc(body))+4096
            need(bound<=(98304 if arm=='A' else 229376),'Approved conservative input reservation')
            entries.append({'case_id':cid,'arm':arm,'body':body,'body_sha256':hashlib.sha256(enc(body)).hexdigest(),'input_bound':bound,
              'packet_bytes':len(enc(packet)),'packet_sha256':sha(OUT/'packets'/f'{cid}_{arm}.json')})
        parity.append({'case_id':cid,'same_actual_sources_text_context_order':True,'native_A_capture':True,
          'selected':12,'delivered':len(a['documents']),'A_bytes':len(enc(a)),'C_bytes':len(enc(c))})
    put(OUT/'projections.json',projections);put(OUT/'requests.json',entries);put(OUT/'packet_parity.json',parity)
    put(OUT/'offline_stage_result.json',{'status':'PASS','external_requests':0,'query_vectors_consumed':len(emb.used),'cases':18,
       'original_sources_preserved':True,'preservation':frozen()})
    print('OFFLINE_STAGE PASS: store3768;18 frozen retrievals;36 packets;0 external calls',flush=True)

def smoke():
    from langchain_core.documents import Document
    q={'question':'synthetic packet fixture','report_scope':{'rcept_no':'fixture'}}
    hits=[(Document(page_content='value '+str(i)+' '+'a'*5500,metadata={'rcept_no':'fixture','chunk_uid':str(i),'unit':'원'}),1/(60+i)) for i in range(12)]
    packet,result=packet_from_native(q,hits)
    need(0<len(packet['documents'])<12 and len(enc(packet))<=65536,'Whole-source omission fixture')
    rows=corpus();samples=[rows[0],next(r for r in rows if r['metadata'].get('table_object_json'))]
    samples=list({r['uid']:r for r in samples}.values());vec={r['text_sha256']:[1.0]+[0.0]*3071 for r in samples}
    check=build_store(samples,vec,OUT/'smoke_store_hydration')
    from src.storage.vector_store import VectorStoreManager
    with patch('src.storage.vector_store.create_embeddings',lambda **kw:CachedEmbeddings({})):
        vsm=VectorStoreManager(persist_directory=str(OUT/'smoke_store_hydration'),collection_name='holdout18_v12_20261023',allow_query_embedding_fallback=False)
    need(vsm.validate_source_integrity()['ready'],'Smoke source integrity')
    for r in samples:
        node=vsm._structure_graph['nodes'][r['uid']];hydrated=vsm._metadata_with_table_payload(node['metadata'])
        if 'table_payload_id' not in r['metadata']:hydrated.pop('table_payload_id',None)
        need(node['text']==r['text'] and hydrated==r['metadata'],'Smoke hydrated parity')
    put(OUT/'offline_stage_smoke_hydration.json',{'status':'PASS','native_packet_omission':True,'source_count':len(packet['documents']),'store':check,'hydrated_source_parity':True,'external_calls':0})
    print('OFFLINE SMOKE PASS',flush=True)

if __name__=='__main__':
    if sys.argv[1]=='smoke':smoke()
    elif sys.argv[1]=='real':real()
    else:raise Stop('Unknown offline mode')
