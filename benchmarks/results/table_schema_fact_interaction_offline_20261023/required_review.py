"""Bounded evaluator-only source review. No retrieval, projection, or model calls.

Search terms below identify passages for manual reading; they never decide
semantic sufficiency or change experiment delivery or frozen criteria.
"""
from __future__ import annotations
import hashlib,json,re,sys
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
BASE=OUT.parent
ARMS=('A12_original','S12_original','A12_fact160','S12_fact160')
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT))
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,data):
 p=(OUT/name).resolve();assert p.is_relative_to(OUT)
 p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

contract=load(OUT/'evaluation_contract.json')
supplement=load(OUT/'evaluation_supplement.json')
cases=list(dict.fromkeys([x['case_id'] for x in supplement['historical26_unit_panel']]+[x['case_id'] for x in supplement['current_nonPASS_case_criteria']]+['LGE_T2_052']))
sources=load(BASE/'table_fact_units_offline_20261023/source_checks.json')
trees={};source_receipts={};geometry_cache={}
def tree(receipt):
 if receipt not in trees:
  from lxml import etree
  from src.processing.financial_parser import _sanitize_xml_like_text
  info=sources[receipt];p=ROOT/info['path'];h=sha(p);assert h==info['sha256']
  clean,changes=_sanitize_xml_like_text(p.read_text(encoding='utf-8'))
  trees[receipt]=etree.fromstring(clean.encode(),etree.XMLParser(no_network=True,resolve_entities=False,recover=False,huge_tree=True)).getroottree()
  source_receipts[receipt]={'path':str(p.relative_to(ROOT)),'sha256':h,'strict_XML_after_existing_sanitizer':True,'sanitizer_changes_in_memory':changes}
 return trees[receipt]
def geometry(receipt,locator):
 key=(receipt,locator)
 if key not in geometry_cache:
  t=tree(receipt);elements=t.xpath(locator);assert len(elements)==1
  occupied=set();out={}
  for r,tr in enumerate(elements[0].xpath('.//TR')):
   c=0
   for cell in tr:
    if cell.tag not in ('TH','TD','TE','TU'):continue
    while (r,c) in occupied:c+=1
    rs=int(cell.get('ROWSPAN','1'));cs=int(cell.get('COLSPAN','1'))
    out[t.getpath(cell)]=[r,c,rs,cs,''.join(cell.itertext()).strip()]
    for rr in range(r,r+rs):
     for cc in range(c,c+cs):occupied.add((rr,cc))
    c+=cs
  geometry_cache[key]=out
 return geometry_cache[key]

def decode(cid,arm,results):
 path=OUT/'packets'/f'{cid}_{arm}.json';packet=load(path);units=[]
 decisions={d['uid']:d for d in results[cid]['arms'][arm].get('decisions',[])}
 for di,doc in enumerate(packet['documents']):
  w=doc.get('table_fact_units')
  if not w:continue
  decision=decisions[doc['chunk_id']];pool=decision['cell_pool_locators']
  attached={u['wire_unit_index']:u for u in decision['units'] if u['status']=='attached'}
  for ui,(r,c,v,ra,ca) in enumerate(w['units']):
   units.append({'document_index':di,'chunk_uid':doc['chunk_id'],'unit_index':ui,'unit_id':attached[ui]['unit_id'],'at':[r,c],
    'value':{'locator':pool[v],'cell':w['cells'][v]},'row_axes':[{'locator':pool[a],'cell':w['cells'][a]} for a in ra],
    'column_axes':[{'locator':pool[a],'cell':w['cells'][a]} for a in ca],
    'frame':{k:v for k,v in w.items() if k not in ('cells','units')},
    'packet_pointer':f'/documents/{di}/table_fact_units/units/{ui}'})
 return packet,units

def verify_unit(unit):
 receipt=unit['chunk_uid'].split(':')[0];f=unit['frame'];t=tree(receipt)
 assert f['document_sha256']==sources[receipt]['sha256']
 g=geometry(receipt,f['table_locator']);norm=[]
 for item in [unit['value']]+unit['row_axes']+unit['column_axes']:
  a=g[item['locator']];b=item['cell'];assert a[:4]==b[:4]
  assert re.sub(r'\s+',' ',a[4])==re.sub(r'\s+',' ',b[4])
  if a[4]!=b[4]:norm.append({'locator':item['locator'],'source':a[4],'wire':b[4]})
 for ctx in f['literal_source_contexts']:
  elems=t.xpath(ctx['source_locator']);assert len(elems)==1
  lo,hi=ctx['source_span'];assert ''.join(elems[0].itertext())[lo:hi]==ctx['source_text']
 return {**unit,'source_physical_check':'EXACT_GEOMETRY_AND_LITERAL_CONTEXTS','whitespace_only_normalizations':norm}

TERMS={
 'NAV_T3_007':['2,578,089,956','19,630,042'],
 'MIX_T3_048':['9,864,474','9,864','9,810,119','9.8','2024년부터','50%','배당금의 지급'],
 'HYU_T2_010':['87.0','78.1','인플레이션','보호무역','미국시장에서'],
 'SKH_T1_060':['52,704,853','3,834,567','4,145,647','10,121,033','9,490,410','29,468,632'],
 'CEL_T3_040':['2,526,280','48,885,812','25,163,510'],
 'MIX_T1_064':['129,179,183','18,357,495','162,663,579'],
 'KBF_T2_043':['3,673,524','3,514,902','1,216','1,146','70,039','자산관리','AUM'],
 'KBF_T2_018':['3,146,409','1,847,775','3,146.4','1,847.8','미래경기','신용손실충당금'],
 'SAM_T1_001':['258,935,494','6,566,976'],
 'CEL_T1_013':['342,736,271','181,624,107'],
 'POS_T1_057':['3,531,423','3,531,422,506,439','1,001,290','영업이익'],
 'HYU_T3_072':['Motional','1,775','803,742','12,115','791,627','700,691','1,294,367'],
 'SKI_T1_068':['581,816','1,903,886'],
 'LGE_T2_052':['1.89','1.62','USD','Lagging']}

def inspect():
 results={x['case_id']:x for x in load(OUT/'results.json')}
 for cid in cases:
  original_docs={};evidence={}
  for arm in ARMS:
   p,units=decode(cid,arm,results);hits=[]
   for di,doc in enumerate(p['documents']):
    uid=doc['chunk_id']
    if arm.endswith('original'):original_docs.setdefault(uid,{'text':doc['text'],'context':doc['context'],'arms':[]})['arms'].append(arm)
    for li,line in enumerate(doc['text'].splitlines()):
     if any(term in line for term in TERMS[cid]):hits.append({'chunk_uid':uid,'line_index':li,'line':line,'text_sha256':hashlib.sha256(doc['text'].encode()).hexdigest()})
   selected=[]
   for u in units:
    labels=[u['value']['cell'][4]]+[x['cell'][4] for x in u['row_axes']+u['column_axes']]
    if any(term in ' '.join(labels) for term in TERMS[cid]):selected.append(verify_unit(u))
   evidence[arm]={'packet_sha256':sha(OUT/'packets'/f'{cid}_{arm}.json'),'text_passages_for_manual_review':hits,'source_verified_candidate_units_for_manual_review':selected,
    'physical_table_inventory':[{'chunk_uid':d['chunk_id'],'table_locator':d['table_fact_units']['table_locator'],'contexts':d['table_fact_units']['literal_source_contexts'],'unit_count':len(d['table_fact_units']['units'])} for d in p['documents'] if 'table_fact_units' in d]}
  save(f'required_review_details/{cid}.json',{'case_id':cid,'query':p['query'],'original_documents':original_docs,'arms':evidence,'term_matches_are_not_semantic_verdicts':True})
 save('required_review_details/source_receipts.json',source_receipts)
 print('Saved bounded review material for',len(cases),'cases')

def source_quote(receipt,quote):
 t=tree(receipt);matches=[]
 for e in t.xpath('//P | //TE | //TD'):
  txt=''.join(e.itertext());at=txt.find(quote)
  if at>=0:matches.append((len(txt),t.getpath(e),txt,at))
 assert matches,(receipt,quote)
 _,loc,txt,at=min(matches)
 return {'document_sha256':sources[receipt]['sha256'],'source_locator':loc,'quote':quote,'source_span':[at,at+len(quote)],'exact_source_match':True,'source_text':txt}

def adjudicate():
 """Manual verdicts, frozen after reading actual rows, headers, contexts and prose."""
 # Read-only recheck each source file used by the prepared unit receipts.
 for receipt in {u['chunk_uid'].split(':')[0] for cid in cases for a in ('A12_fact160','S12_fact160') for u in load(OUT/f'required_review_details/{cid}.json')['arms'][a]['source_verified_candidate_units_for_manual_review']}:tree(receipt)
 details={cid:load(OUT/f'required_review_details/{cid}.json') for cid in cases}
 results={x['case_id']:x for x in load(OUT/'results.json')}
 old=load(BASE/'table_fact_budget77_offline_20261023/postrun_required_fact_review.json')
 old_units={(c['case_id'],u['unit_id']):u for c in old['legacy26_panel'] for u in c['units']}
 # These source-coordinate selections record manually read evidence. They are
 # evaluator-only receipts, not an automatic number/UID sufficiency detector.
 selections={
  ('NAV_T3_007','goodwill_end'):[('20240318000844:353:229',[9,4])],
  ('NAV_T3_007','impairment'):[('20240318000844:353:229',[6,4])],
  ('MIX_T3_048','cash_dividend'):[('20240312000736:127:6',[33,1])],
  ('SKH_T1_060','borrowings'):[('20240319000684:277:148',x) for x in [[1,1],[5,1],[6,1],[8,1]]],
  ('SKH_T1_060','short_borrowing'):[('20240319000684:277:148',[1,1])],
  ('SKH_T1_060','long_borrowing'):[('20240319000684:277:148',[5,1])],
  ('SKH_T1_060','bond'):[('20240319000684:277:148',[6,1])],
  ('CEL_T3_040','inventory_loss'):[('20240318000913:517:357',[4,2])],
  ('CEL_T3_040','inventory_reversal'):[('20240318000913:517:357',[5,2])],
  ('CEL_T3_040','inventory_disposal'):[('20240318000913:517:357',[6,2])],
  ('MIX_T1_064','cost_of_sales'):[('20240313001451:1047:3',[2,1])],
  ('MIX_T1_064','selling_admin'):[('20240313001451:408:266',[1,3])],
  ('MIX_T1_064','revenue'):[('20240313001451:1047:3',[1,1])],
  ('KBF_T2_043','fee_current'):[('20240326000894:625:2',[2,1])],
  ('KBF_T2_043','fee_prior'):[('20240326000894:625:2',[2,2])],
  ('KBF_T2_043','wm_group'):[('20240326000894:1845:4',x) for x in [[2,2],[2,3],[2,4]]],
  ('KBF_T2_018','provision_current'):[('20240326000894:625:2',[9,1]),('20240326000894:1846:5',[8,1])],
  ('KBF_T2_018','provision_prior'):[('20240326000894:625:2',[9,2]),('20240326000894:1846:5',[8,3])],
  ('SAM_T1_001','revenue'):[('20240312000736:123:2',[1,1]),('20240312000736:677:4',[1,1])],
  ('SAM_T1_001','operating_income'):[('20240312000736:123:2',[5,1]),('20240312000736:677:4',[5,1])],
  ('CEL_T1_013','rd_total'):[('20240318000913:101:42',[6,2])],
  ('CEL_T1_013','rd_capitalized'):[('20240318000913:101:42',[10,2])],
  ('POS_T1_057','interest_cost'):[('20240322000986:692:331',[12,1])],
  ('HYU_T3_072','ownership'):[('20240313001451:1246:4',[143,12]),('20240313001451:275:133',[3,4]),('20240313001451:687:106',[2,4])],
  ('HYU_T3_072','carrying'):[('20240313001451:1246:4',[143,13]),('20240313001451:275:133',[3,5]),('20240313001451:687:106',[2,5])],
  ('SKI_T1_068','battery_loss'):[('20240320000950:1713:6',[12,2]),('20240320000950:882:499',[8,22])],
  ('SKI_T1_068','total_operating_income'):[('20240320000950:1713:6',[24,2]),('20240320000950:882:499',[8,27])],
  ('SKI_T1_068','currency_binding'):[('20240320000950:1713:6',[12,2]),('20240320000950:1713:6',[24,2]),('20240320000950:882:499',[8,22]),('20240320000950:882:499',[8,27])],
 }
 prose={
  ('MIX_T3_048','return_policy'):('20240312000736:590:0','당사는 2024년부터 2026년까지 3년간 발생하는 잉여현금흐름의 50%'),
  ('HYU_T2_010','sales_current'):('20240313001451:96:5','2023년 미국시장에서 현대차는 전년 대비 11.5% 증가한 87.0만 대'),
  ('HYU_T2_010','sales_prior'):('20240313001451:96:5','2022년에는 전년 대비 0.9% 감소한 78.1만 대'),
  ('HYU_T2_010','protectionism'):('20240313001451:1058:14','미국의 인플레이션 감축법과 유럽의 핵심원자재법'),
  ('KBF_T2_018','risk_cause'):('20240326000894:1846:5','신용손실충당금전입액은 미래경기 불확실성에 대비한 보수적인 충당금적립으로'),
 }
 notes={
  'NAV_T3_007':'The goodwill column, not total intangible assets, supplies closing2,578,089,956 and impairment/reversal(19,630,042)천원. 당기 is the preserved source period; no calendar inferred from metadata.',
  'MIX_T3_048':'A12 actually delivers connected cash-flow dividend outflow(9,864,474)백만원. Both S12 arms retain only separate(9,810,119) plus declared-dividend disclosures. No source-equivalent connected actual-payment alternative exists in the inspected S12 packet/table inventory. Return-policy prose preserves2024-2026, FCF50%, annual9.8조원 and conditional remaining-capital return in every arm.',
  'HYU_T2_010':'The frozen conditional Hyundai-subject panel requires87.0/78.1만대 with explicit2023/2022. Both S12 arms retain US total-market1,560.8만대/12.3% and IRA-response prose but lack Hyundai sales operands. Total market cannot replace Hyundai. HOLD for omitted question subject is retained; no answer-completion credit.',
  'SKH_T1_060':'Connected current named debt operands4,145,647+10,121,033+9,490,410=23,757,090백만원 remain.29,468,632 includes current reclassifications and is recorded only as the legacy explained alternative. No selected borrowing physical table supplies closing PPE52,704,853 or intangible3,834,567; collateral and acquisition amounts cannot substitute. No full case recovery.',
  'CEL_T3_040':'The connected current cash-flow adjustment rows separately preserve gross loss2,526,280, reversal(48,885,812), disposal25,163,510천원. Reversal sign and meaning are retained; no netting or separate-note substitution.',
  'MIX_T1_064':'Connected MD&A current revenue162,663,579 and cost129,179,183백만원 plus connected current SG&A18,357,495 remain. 제56기 and 당기 are kept as displayed; the original MD&A includes current2023 results prose.',
  'KBF_T2_043':'Connected summary fees3,673,524/3,514,902백만원 and group AUM1,216,729/1,146,691 with70,039십억원 growth remain. Group AUM includes balance-sheet assets and entrusted assets; it is not WM-only performance. Subsidiary broker WM amounts are not a replacement. Existing HOLD remains despite conditional panel availability.',
  'KBF_T2_018':'Connected provision rows(3,146,409)/(1,847,775)백만원 remain, with explicit2023/2022 rounded3146/1848십억원 alternatives and direct conservative-provisioning cause. Lost662:19 worse/crisis elaboration does not remove required causal prose1846:5.',
  'SAM_T1_001':'Connected revenue258,935,494 and operating income6,566,976백만원 remain in both original packets. Fact appendices add explicit calendar/caption context but no new required numbers.',
  'CEL_T1_013':'Connected current 제33기 research expense total342,736,271 and capitalized development181,624,107천원 remain. Rows and source disclosure identify connected basis; no mixing with subsidiary R&D totals.',
  'POS_T1_057':'Connected current interest1,001,290백만원 remains. S12 adds1417:255 operating income110,563,784,581원, whose actual source owner is POSCO DX (sourceP570); this is not POSCO Holdings connected3,531,422,506,439원/3,531,423백만원. Actual source-supported alternative fails subject equivalence, so operating-income requirement remains absent.',
  'HYU_T3_072':'A12_fact160 has the2023.12.31 investment-table closing25.81%/1,294,367백만원 alternative. Its source heading does not literally certify separate-financial-statement scope. S12 instead retains directly labelled connected26%/700,691 and separate25.81%/1,294,367 in275:133/687:106 with source 당기 context. Prior-period294:152 carrying907,061 is rejected as current alternative. No arm supplies the frozen named four-cell profit summary. S12 loses the supplementary investment-row netprofit-803,742 through budget, but does not lose the ownership/carrying requirement because equivalents remain.',
  'SKI_T1_068':'All arms contain battery loss(581,816) and total1,903,886 rows. S12_original adds882:499 with source-correct unit_hint 백만원, but under the explicit frozen currency_binding requirement this hint is not the actual literal source_context. Both fact160 arms deliver actual linked 백만원 captions for1713:6/304:4; S12 also does so for882:499. Treat this as mandatory-axis recovery, not new numbers. Relative 당기 on882 does not invent a calendar.',
 }
 def receipts(cid,unit):
  output={}
  for arm in ARMS:
   a=details[cid]['arms'][arm];enhanced=arm.replace('_original','_fact160')
   actual=a['source_verified_candidate_units_for_manual_review']
   records=[x for x in actual if any(x['chunk_uid']==uid and x['at']==at for uid,at in selections.get((cid,unit),[]))]
   bodies=[]
   for uid,at in selections.get((cid,unit),[]):
    doc=details[cid]['original_documents'].get(uid)
    if not doc or arm.split('_')[0]+'_original' not in doc['arms']:continue
    # Source coordinates from the separately checked appendix identify source
    # origin; actual original delivery is certified by the quoted body line.
    source_candidates=[x for x in details[cid]['arms'][enhanced]['source_verified_candidate_units_for_manual_review'] if x['chunk_uid']==uid and x['at']==at]
    for sc in source_candidates:
     value=sc['value']['cell'][4]
     for h in a['text_passages_for_manual_review']:
      if h['chunk_uid']==uid and not h['line'].startswith('[') and value in h['line']:
       bodies.append({**h,'source_coordinate_receipt':{'table_locator':sc['frame']['table_locator'],'document_sha256':sc['frame']['document_sha256'],'value_locator':sc['value']['locator'],'at':at},'semantic_role':'manually_checked_named_row_and_column'})
   if (cid,unit) in prose:
    uid,q=prose[cid,unit]
    for h in a['text_passages_for_manual_review']:
     if h['chunk_uid']==uid and q in h['line'] and not h['line'].startswith('['):bodies.append({**h,'source_receipt':source_quote(uid.split(':')[0],q)})
   output[arm]={'packet_sha256':a['packet_sha256'],'actually_delivered_appendix_units':records,'original_body_passages':bodies,'details_file':f'required_review_details/{cid}.json'}
  return output
 def unit_record(cid,u,states,kind):
  key=(cid,u['unit_id']);prior=old_units.get(key,{})
  d={'unit_id':u['unit_id'],'unchanged_criterion':u['unchanged_criterion'],'present_with_required_relationship_by_arm':dict(zip(ARMS,states)),
   'value_or_relation':prior.get('value_or_relation',u.get('prior_value_or_relation')),'source_axes':prior.get('axes',u.get('prior_axes')),
   'review_note':notes[cid],'evidence':receipts(cid,u['unit_id']),'physical_certainty':'Located selected facts rechecked against hash-matched original XML cells, headers and literal context spans; packet paths/hashes are exact.',
   'semantic_certainty':'Manual bounded source review of the frozen unit, not model-read/answer correctness or universal axis certification.',
   'calendar_rule':'Literal relative periods retained; no absolute year supplied from filing metadata alone.',
   'new_vs_duplicate':kind,'pairs':{}}
  for name,left,right in [('retrieval_original',0,1),('A12_delivery',0,2),('S12_delivery',1,3),('retrieval_fact160',2,3)]:
   d['pairs'][name]='NEW_REQUIRED_VALUE_OR_RELATION' if not states[left] and states[right] else 'REQUIRED_EVIDENCE_LOSS' if states[left] and not states[right] else 'ALREADY_AVAILABLE' if states[left] else 'NO_RECOVERY'
  return d
 legacy=[]
 for c in supplement['historical26_unit_panel']:
  cid=c['case_id'];units=[]
  for u in c['units']:
   states=[True]*4
   if cid=='SKH_T1_060' and u['unit_id'] in ('ppe','intangible'):states=[False]*4
   if cid=='MIX_T3_048' and u['unit_id']=='cash_dividend':states=[True,False,True,False]
   if cid=='HYU_T2_010' and u['unit_id'] in ('sales_current','sales_prior'):states=[True,False,True,False]
   units.append(unit_record(cid,u,states,'No new legacy required values from either delivery package; existing values, bound-context enrichment, or retained absence.'))
  legacy.append({'case_id':cid,'group':c['group'],'units':units,'complete_conditional_evidence_by_arm':{a:all(u['present_with_required_relationship_by_arm'][a] for u in units) for a in ARMS},'HOLD_lifted':False})
 current=[]
 for c in supplement['current_nonPASS_case_criteria']:
  cid=c['case_id'];units=[]
  for u in c['units']:
   uid=u['unit_id'];states=[True]*4
   if uid in ('ppe','intangible','profit_summary') or cid=='POS_T1_057' and uid=='operating_income':states=[False]*4
   if cid=='HYU_T3_072' and uid in ('ownership','carrying'):states=[False,True,True,True]
   if cid=='SKI_T1_068' and uid=='currency_binding':states=[False,False,True,True]
   r=unit_record(cid,u,states,'BOUND_CONTEXT_ENRICHMENT or duplicated row when already present; raw-caption recovery is an axis, not a value.')
   if cid=='SKI_T1_068' and uid=='currency_binding':
    r['pairs']['A12_delivery']=r['pairs']['S12_delivery']='NEW_MANDATORY_AXIS'
    r['S12_original_distinction']={'correct_unit_hint':'백만원','physical_source_unit_matches_hint':True,'literal_source_context_actually_delivered':False,'strict_frozen_currency_binding_complete':False,'classification':'HINT_ONLY_NOT_LITERAL_CONTEXT_DELIVERY'}
   units.append(r)
  current.append({'case_id':cid,'group':'common_answerable','units':units,'complete_required_evidence_by_arm':{a:all(u['present_with_required_relationship_by_arm'][a] for u in units) for a in ARMS},'finding':notes[cid]})
 # Deliberately separate supplementary fact loss from frozen unit completion.
 motional={'supplementary_net_profit':{}}
 for arm in ('A12_fact160','S12_fact160'):
  u=[x for x in details['HYU_T3_072']['arms'][arm]['source_verified_candidate_units_for_manual_review'] if x['value']['cell'][4]=='-803,742']
  ds=[]
  for dec in results['HYU_T3_072']['arms'][arm]['decisions']:
   for item in dec.get('units',[]):
    if item.get('at')==[143,15] and 'SECTION-1[13]' in dec.get('physical_key',''):ds.append({'owner_uid':dec['uid'],**item})
  motional['supplementary_net_profit'][arm]={'actually_delivered':bool(u),'receipts':u,'decisions':ds}
 motional['classification']='SUPPLEMENTARY_PARTIAL_PROFIT_RELATION_LOSS; frozen profit_summary incomplete in both arms; ownership/carrying retained by source-equivalent alternatives.'
 # Original source row locators also establish what the incomplete summary
 # would require; these reviewer-only receipts are not delivered packet facts.
 ht=tree('20240313001451');loc='/DOCUMENT/BODY/SECTION-1[4]/LIBRARY/SECTION-2[2]/TABLE-GROUP[13]/TABLE[28]/TBODY/TR[5]'
 motional['missing_frozen_summary_source']={'document_sha256':sources['20240313001451']['sha256'],'source_row_locator':loc,'literal_row':' | '.join(''.join(x.itertext()).strip() for x in ht.xpath(loc)[0]),'not_delivered_in_any_arm':True}
 pt=tree('20240322000986');pl='/DOCUMENT/BODY/SECTION-1[5]/P[570]'
 pos_owner={'source_locator':pl,'document_sha256':sources['20240322000986']['sha256'],'literal_text':''.join(pt.xpath(pl)[0].itertext()),'reason':'Source owner of1417:255 is POSCO DX; unknown parent metadata cannot certify POSCO Holdings group equivalence. This owner label was reviewed from source, not asserted to be transmitted.'}
 lge=details['LGE_T2_052'];lge_records={}
 for a in ARMS:
  lge_records[a]={'product_price_USD_bound':a!='S12_original','product_prices':'1.89/1.62 under literal제4기/제3기; single-customer supply price, not overall battery ASP',
   'receipt':[u for u in lge['arms'][a]['source_verified_candidate_units_for_manual_review'] if u['chunk_uid']=='20240314001110:21:2'],
   'raw_material_and_lagging_note':'Original24:2/23:1 raw-material prices and897:3 lagging relationship remain; do not borrow raw-material USD for product table21:2.'}
 summary={}
 for a in ARMS:
  summary[a]={'legacy_common_present':sum(u['present_with_required_relationship_by_arm'][a] for c in legacy if c['group']=='common_answerable' for u in c['units']),
   'legacy_common_denominator':20,'legacy_common_complete_cases':sum(c['complete_conditional_evidence_by_arm'][a] for c in legacy if c['group']=='common_answerable'),'legacy_common_case_denominator':8,
   'legacy_HOLD_present':sum(u['present_with_required_relationship_by_arm'][a] for c in legacy if c['group']=='diagnostic_or_hold' for u in c['units']),
   'legacy_HOLD_denominator':6,'legacy_HOLD_conditional_complete_cases':sum(c['complete_conditional_evidence_by_arm'][a] for c in legacy if c['group']=='diagnostic_or_hold'),'legacy_HOLD_case_denominator':2,
   'current4_required_units_present':sum(u['present_with_required_relationship_by_arm'][a] for c in current for u in c['units']),'current4_unit_denominator':13,
   'current4_complete_cases':sum(c['complete_required_evidence_by_arm'][a] for c in current),'current4_case_denominator':4}
 paths=[OUT/'protocol.json',OUT/'evaluation_contract.json',OUT/'evaluation_supplement.json',OUT/'results.json',BASE/'table_schema_search_validated_offline_20261022/known_witness_panel.json',BASE/'table_schema_search_validated_offline_20261022/source_review.json',BASE/'table_fact_budget77_offline_20261023/postrun_required_fact_review.json']
 report={'schema_version':'bounded_required_evidence_source_review_v1','status':'COMPLETE_BOUNDED_SOURCE_REVIEW','date':'2026-10-23',
  'reviewer':'Delegated Codex source reviewer; fork_turns=none; requested model gpt-6-astra and reasoning_effort=xhigh under ARS policy; provider-attested actual model identity unavailable. Development-exposed, unblinded source review; no new peer answers read.',
  'scope':'legacy26 facts across10 cases, overlapping current4 nonPASS requirements, plus supplemental LGES product-price currency binding; all four actual saved arms.',
  'method':'Frozen criteria, manually interpreted row/column/prose relationships and source-equivalent alternatives. Candidate substring searches only located passages; manual decisions above determine sufficiency. Original XML hashes and source receipts rechecked. No generated answers.',
  'arms':list(ARMS),'input_hashes':{str(p.relative_to(ROOT)):sha(p) for p in paths},'packet_hashes':{f'{cid}_{a}':details[cid]['arms'][a]['packet_sha256'] for cid in cases for a in ARMS},
  'summary':summary,'legacy26_panel':legacy,'current4':current,'Motional_supplementary_relation_change':motional,'POSCO_non_equivalent_subject_receipt':pos_owner,
  'LGES_supplemental_product_price_binding':lge_records,
  'paired_conclusion':{'A12_original_to_A12_fact160':'Current4: Motional ownership/carrying partial recovery and SKI mandatory monetary caption recovery. No new legacy26 numeric/required relation.',
   'S12_original_to_S12_fact160':'Current4: SKI literal monetary-caption recovery under strict frozen criterion. LGES product USD restored; no new legacy26 required fact. Motional remains incomplete.',
   'A12_fact160_to_S12_fact160':'Legacy common actual Samsung dividend lost1unit; HOLD conditional Hyundai US sales lost2units. Current4 complete-case counts unchanged; Motional ownership/carrying alternatives retained, extra investment-row netprofit lost. LGES product USD parity. No new frozen required unit on this bounded panel.',
   'gate':'DO_NOT_ADVANCE_ON_THIS_PANEL: confirmed required-evidence regression remains. Whole77 general conclusions belong to parent integration.'},
  'source_files_rechecked':source_receipts,
  'unresolved_and_limits':['Relative periods remain relative unless the actual delivered source supplies calendar mapping.','HOLD question definitions remain unresolved and their conditional completeness is never ordinary-answer recovery.','Motional four-item named profit summary remains absent; separate investment-table net profit is incomplete and its S12 loss is separately reported.','SKH asset denominators and POSCO Holdings group operating income remain absent, not proven absent from reports.','S12_original SKI source-correct unit_hint is a hint-only observation; it does not satisfy the specifically frozen delivered literal-source-context requirement.','Physical source checks do not certify interpretation by a model, answer correctness, semantic faithfulness, refusal behavior or generalization.','No fresh model calls, retrieval, projector execution, runtime/store/.env changes or criterion changes were performed.']}
 save('required_evidence_review.json',report)
 save('required_review_details/source_receipts.json',source_receipts)
 print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='adjudicate':adjudicate()
 else:inspect()
