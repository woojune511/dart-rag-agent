import json,re,hashlib,collections
from pathlib import Path
from lxml import etree
from src.processing.financial_parser import _sanitize_xml_like_text
p=Path('benchmarks/results/table_bundle_delivery_offline_20261022')
b=json.loads((p/'bundles.json').read_text(encoding='utf-8'));r=json.loads((p/'results.json').read_text(encoding='utf-8'));source=json.loads((p/'source_checks.json').read_text(encoding='utf-8'))
sha=lambda x:hashlib.sha256(x).hexdigest()
compact=lambda x:json.dumps(x,ensure_ascii=False,sort_keys=True,allow_nan=False,separators=(',',':')).encode()
norm=lambda x:re.sub(r'[ \t]+',' ',x).strip()
issues=[];packet_checks=[];attached=set();decisions=collections.Counter();budget_details=[]
for row in r:
 cid=row['case_id'];a=json.loads((p/'packets'/f'{cid}_A12.json').read_text(encoding='utf-8'));t=json.loads((p/'packets'/f'{cid}_T12.json').read_text(encoding='utf-8'))
 stripped={**t,'documents':[{k:v for k,v in d.items() if k!='table_evidence'} for d in t['documents']]}
 ok=a==stripped
 if not ok:issues.append({'kind':'original_packet_changed','case_id':cid})
 pb=len(compact(t));ab=len(compact(a));ats=[]
 for d in t['documents']:
  if 'table_evidence' in d:
   uid=d['chunk_id'];attached.add(uid);ats.append(uid)
   if d['table_evidence']!=b[uid]['bundle']:issues.append({'kind':'attached_bundle_changed','uid':uid})
 if pb>65536 or pb!=row['experimental_bytes'] or ab!=row['baseline_bytes']:issues.append({'kind':'packet_bytes','case_id':cid,'bytes':pb})
 if sha(compact(a))!=row['baseline_packet_sha256'] or sha(compact(t))!=row['experimental_packet_sha256']:issues.append({'kind':'packet_hash','case_id':cid})
 expected=[d['uid'] for d in row['decisions'] if d['status']=='attached']
 if ats!=expected:issues.append({'kind':'attached_status_order','case_id':cid})
 packet_checks.append({'case_id':cid,'original_packet_exact_after_removing_table_evidence':ok,'original_source_count':len(a['documents']),'added_bundle_count':len(ats),'baseline_bytes':ab,'experimental_bytes':pb,'byte_cap_pass':pb<=65536})
 for d in row['decisions']:
  decisions[d['status']]+=1
  if d['status']=='rejected_byte_budget':budget_details.append({'case_id':cid,'uid':d['uid']})
trees={};sources=[]
for receipt,rec in source.items():
 raw=Path(rec['path']).read_bytes();hs=sha(raw);clean,count=_sanitize_xml_like_text(raw.decode('utf-8'));parser=etree.XMLParser(recover=False,encoding='utf-8',huge_tree=True,no_network=True,resolve_entities=False);tree=etree.ElementTree(etree.fromstring(clean.encode(),parser));trees[receipt]=tree
 sources.append({'receipt':receipt,'raw_sha256':hs,'expected_sha256':rec['sha256'],'sha_match':hs==rec['sha256'],'strict_parse_errors':len(parser.error_log)})
 if hs!=rec['sha256']:issues.append({'kind':'source_hash','receipt':receipt})
physical_keys=set();bundle_checks=[];cell_count=0;coordinate_count=0;contexts_count=0
allowed={'document_sha256','table_locator','grid_coordinate_system','grid','declared_header_row_indices','literal_source_contexts','axis_semantics'}
for uid in sorted(attached):
 item=b[uid];bu=item['bundle'];rc=item['receipt'];tree=trees[uid.split(':')[0]];path=bu['table_locator'];ns=tree.xpath(path)
 start=len(issues);physical_keys.add(item['physical_key'])
 if len(ns)!=1:issues.append({'kind':'table_locator_count','uid':uid});continue
 table=ns[0]
 if set(bu)!=allowed:issues.append({'kind':'unexpected_bundle_fields','uid':uid,'keys':list(set(bu)-allowed)})
 if bu['document_sha256']!=source[uid.split(':')[0]]['sha256']:issues.append({'kind':'bundle_document_hash','uid':uid})
 if table.findall('.//TABLE'):issues.append({'kind':'nested_table_in_attached_bundle','uid':uid})
 trs=table.findall('.//TR');occupancy={};rawcell={};declared=[]
 for ri,tr in enumerate(trs):
  cells=[c for c in tr if c.tag in {'TD','TH','TU','TE'}]
  if any(x.tag=='THEAD' for x in tr.iterancestors() if x is not table) or (cells and all(x.tag=='TH' for x in cells)):declared.append(ri)
  ci=0
  for c in cells:
   while (ri,ci) in occupancy:ci+=1
   rs=int(c.get('ROWSPAN',c.get('rowspan','1')));cs=int(c.get('COLSPAN',c.get('colspan','1')));loc=tree.getpath(c);value=norm(''.join(c.itertext()))
   rawcell[loc]=(ri,ci,rs,cs,value)
   for rr in range(ri,ri+rs):
    for cc in range(ci,ci+cs):
     if (rr,cc) in occupancy:issues.append({'kind':'raw_span_collision','uid':uid,'cell':loc})
     occupancy[(rr,cc)]=loc
   ci+=cs
 width=max(c for _,c in occupancy)+1;rawrows=[[rawcell[occupancy[(rr,cc)]][4] if (rr,cc) in occupancy else '' for cc in range(width)] for rr in range(len(trs))];kept=[i for i,row in enumerate(rawrows) if any(x.strip() for x in row)];grid=[rawrows[i] for i in kept]
 if grid!=bu['grid']:issues.append({'kind':'grid_raw_xml_mismatch','uid':uid})
 if [kept.index(i) for i in declared if i in kept]!=bu['declared_header_row_indices']:issues.append({'kind':'declared_header_mismatch','uid':uid})
 if kept!=rc['raw_row_mapping']['kept_source_tr_indices']:issues.append({'kind':'row_mapping_mismatch','uid':uid})
 cmap={x['cell_locator']:x for x in rc['cell_mapping']}
 for loc,(rr,cc,rs,cs,val) in rawcell.items():
  if not val:continue
  cell_count+=1;expected=[[kept.index(r0),c0] for r0 in range(rr,rr+rs) for c0 in range(cc,cc+cs) if r0 in kept];coordinate_count+=len(expected)
  x=cmap.get(loc)
  if x is None or x['value']!=val or x['expanded_coordinates']!=expected or x['source_tr_index']!=rr or x['source_column_start']!=cc or x['rowspan']!=rs or x['colspan']!=cs or not x['payload_witnesses']:issues.append({'kind':'cell_receipt_mapping_mismatch','uid':uid,'cell':loc})
 for c in bu['literal_source_contexts']:
  contexts_count+=1;nn=tree.xpath(c['source_locator']);sp=c['source_span']
  if c['relation'] not in {'ancestor_heading','intermediate_heading','caption','preceding_block'}:issues.append({'kind':'excluded_relation_added','uid':uid,'relation':c['relation']})
  if len(nn)!=1 or ''.join(nn[0].itertext())[sp[0]:sp[1]]!=c['source_text']:issues.append({'kind':'context_span_mismatch','uid':uid,'context':c['source_locator']})
 if 'not a certified semantic assignment' not in bu['axis_semantics']:issues.append({'kind':'missing_semantic_boundary_notice','uid':uid})
 bundle_checks.append({'uid':uid,'physical_key':item['physical_key'],'raw_source_grid_and_declared_headers_match':not any(x['kind'] in ('grid_raw_xml_mismatch','declared_header_mismatch') for x in issues[start:]),'nonempty_physical_cells':sum(bool(x[4]) for x in rawcell.values()),'literal_context_count':len(bu['literal_source_contexts']),'issue_count':len(issues)-start})
rejections=[]
for row in r:
 for d in row['decisions']:
  if d['status']=='rejected_structural_validation':
   rejections.append({'case_id':row['case_id'],'uid':d['uid'],'reason':b[d['uid']]['receipt']['reason'],'detail':b[d['uid']]['receipt'].get('detail')})
out={'schema_version':'table_bundle_delivery_postrun_axis_author_review_v1','review_type':'AUTHOR_REVIEW_NOT_INDEPENDENT_PROJECTOR_AUDIT','scope':'Read-only static audit of saved A12/T12 packets, appended bundles and original sanitized XML. Does not rerun projector, retrieval or answer generation. Same author helped design and implement projector.','status':'IN_PROGRESS_CASE_SEMANTIC_REVIEW_PENDING','artifact_hashes':{x:sha((p/x).read_bytes()) for x in ['protocol.json','freeze.json','projector.py','bundles.json','results.json','evaluation_contract.json']},'api_calls':0,'new_retrieval_or_model_runs':0,'projector_reruns':0,'source_open_mode':'read-only bytes; in-memory sanitize and strict no-network XML parse','all_packet_preservation_checks':packet_checks,'all_attached_bundle_raw_checks':bundle_checks,'raw_source_checks':sources,'summary':{'cases':len(r),'case_attachment_events':decisions['attached'],'unique_attached_chunk_payloads':len(attached),'unique_attached_physical_tables':len(physical_keys),'nonempty_physical_cells_checked_across_unique_payloads':cell_count,'expanded_nonempty_coordinates_checked_across_unique_payloads':coordinate_count,'literal_contexts_checked_across_unique_payloads':contexts_count,'confirmed_wrong_new_physical_links':len(issues),'original_packet_preserved_cases':sum(x['original_packet_exact_after_removing_table_evidence'] for x in packet_checks),'decisions':dict(decisions)},'physical_check_issues':issues,'skipped_structural_bundle_events':rejections,'byte_budget_skip_events':budget_details,'limitations':['Raw correspondence and packet preservation do not certify semantic adjacency, intended entity scope, question resolution or answer improvement.','Static audit uses the same author and shares design context; not blind or independent.','Original text/context were preserved including misleading pre-existing metadata; safety of model interpretation is unmeasured.','Stored payload completeness was adjudicated by the frozen projector and receipts; this review independently checks raw XML correspondence, not a second complete payload-admission implementation.']}
(p/'postrun_axis_review.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(out['summary'],ensure_ascii=False,indent=2));print('issues',issues[:12]);print('rejection_reason_counts',dict(collections.Counter(x['reason'] for x in rejections)))
