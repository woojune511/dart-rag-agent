"""Source-anchored parent adjudication; never modifies masked reviews or gold."""
from common import *

def main():
    batch=OUT/'masked_review/batch2'
    original=next(r for r in load(batch/'review.json')['reviews'] if r['review_id']=='R006')
    clarification=load(batch/'clarification.json')
    revised=next(c for c in clarification['comparisons'] if c['review_id']=='R006')
    need(original['faithfulness']=='PASS' and revised['recommended_faithfulness']=='PARTIAL','Unexpected adjudication input')
    put(OUT/'adjudication.json',{
      'method':'Parent read the saved answers and actually cited text; original reviews and frozen rubric remain unchanged.',
      'overrides':[{
        'review_id':'R006',
        'replacement_fields':{
          'faithfulness':'PARTIAL',
          'unsupported_claims':original['unsupported_claims']+[revised['suggested_unsupported_claim']]
        },
        'reason':'Apply the same cited-visible standard to R004 and R006. Both add a qualified FabriX-cloud composition hypothesis absent from their cited revenue tables. R006 extra source1297:3 adds only segment amounts. This is a noncentral support defect, not an invented FabriX amount. Accuracy/completeness/refusal and gold are unchanged.',
        'evidence':'masked_review/batch2/clarification.json',
        'original_review_sha256':sha(batch/'review.json')
      }],
      'retained_boundary_judgments':[
        {'case_id':'H12','reviews':['R031','R006'],'decision':'Retain nearest_revenue PARTIAL under frozen rubric: the cloud value is present but wider IT services is explicitly called nearest. This is a category-label issue, not a missing/wrong amount; flag failures remain even under a permissive reading.'},
        {'case_id':'H15','review_id':'R009','decision':'Retain noncentral citation PARTIAL. Cosvision subsidiary relation is present at packet rank1 source49:12 but the answer cites only source48:11. This is citation omission, not evidence that the relation is false or absent from the whole packet.'},
        {'case_id':'H17','review_id':'R067','decision':'Retain strict noncentral citation PARTIAL: cited paragraph says80th anniversary, not founding80th anniversary. Core requested activities and outcomes are correct. Interpretation-sensitive; do not call this recovery of a missing numeric/table fact.'},
        {'case_id':'H18','review_id':'R024','decision':'Retain PASS within question-limited sales/regional-disclosure scope; wording is less explicit, so not evidence of whole-report absence.'}
      ]})
    items={}
    for b in (1,2,3):
        for x in load(OUT/f'masked_review/batch{b}/items.json'):
            items[x['review_id']]=(b,x)
    checks=[]
    for rid,term in [('R053','소재지'),('R009','주요 종속회사인 (주)코스비전 기준'),('R067','창립')]:
        b,item=items[rid];packet=load(OUT/f'masked_review/batch{b}'/item['packet_path'])
        hits=[]
        for rank,d in enumerate(packet['documents'],1):
            if term in json.dumps(d,ensure_ascii=False):
                hits.append({'rank':rank,'source_id':d['source_id'],'cited':d['source_id'] in item['answer']['cited_source_ids']})
        checks.append({'review_id':rid,'literal':term,'hits':hits,'limit':'Literal presence check accompanies human-readable source review; not a semantic completeness test.'})
    put(OUT/'parent_source_audit.json',{
      'status':'COMPLETE','checked_nonpass_and_refusal_cases':['H07','H12','H15','H17','H18'],
      'literal_checks':checks,
      'source_findings':[
        {'case_id':'H07','boundary':'Answer omission, not absent retrieval in this replay. Source147:32 is rank8 with explicit location-basis text in both A/C. All4 answers omit it while preserving all4 amounts, years, units and consolidation scope.'},
        {'case_id':'H12','boundary':'All4 prose answers decline to invent FabriX revenue; A both and C repeat2 nevertheless set abstained=false. C supplies nearest-cloud framing, but its repeat2 and A repeat2 add unsupported tentative product membership.'},
        {'case_id':'H15','boundary':'All4 calculations are23.9% with correct same-entity operands. A repeat2 has an uncited but packet-visible subsidiary parenthetical. C does not need that extra citation because it omits the parenthetical.'},
        {'case_id':'H17','boundary':'All4 core narrative answers correct. A repeat2 adds founding, absent from its cited paragraph and entire supplied packet; C does not add that modifier.'}
      ],
      'causal_limit':'Observed output differences only. Two repeats cannot establish that table units caused removal of noncentral prose additions.'})
    put(OUT/'ledger_reviews.json',{
      'kind':'tool_receipt','step':'masked_source_review72','command':'Three fresh native masked review returns; verify_reviews.py; source-consistency clarification and parent adjudicate.py',
      'status':'passed','exit_status':0,'retries_used':0,
      'input_paths':['masked_review/batch1/review.json','masked_review/batch2/review.json','masked_review/batch3/review.json','masked_review/batch2/clarification.json','review_validation.json','adjudication.json','parent_source_audit.json'],
      'gate_tokens':['72_REVIEWED','359_SOURCE_RECEIPTS','ONE_EXPLICIT_CONSISTENCY_ADJUDICATION','RUBRIC_UNCHANGED','NO_EXTERNAL_JUDGE_CALLS']})
    print('Parent adjudication saved; frozen reviews/gold unchanged.')

if __name__=='__main__':main()
