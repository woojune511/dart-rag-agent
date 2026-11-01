"""Source-bound dataset assembly, exact witness and arithmetic validation; no calls."""
from common import *
import re, copy
from collections import Counter
from decimal import Decimal, localcontext, ROUND_HALF_UP
from fractions import Fraction
from lxml import etree
def main():
    assert not (BASE/'freeze.json').exists(), 'Frozen preparation may not be overwritten'
    rows=sum((read(BASE/f'{label}_questions.json') for label in ('kia','sds','amore')),[])
    adjudication=read(BASE/'gold_adjudication.json')
    assert adjudication['status']=='RESOLVED_BEFORE_RETRIEVAL_OR_ANSWERS'
    for change in adjudication['changes']:
        q=next(q for q in rows if q['case_id']==change['case_id'])
        fact=next(f for f in q['required_facts'] if f['id']==change['fact_id'])
        assert {key:fact[key] for key in change['before']}==change['before']
        fact.update(change['after'])
        q['optional_items'].append(change['append_optional'])
    assert [q['case_id'] for q in rows]==[f'H{i:02}' for i in range(1,19)]
    assert Counter(q['kind'] for q in rows)=={'numeric_direct':6,'calculation':3,'mixed':3,'narrative':3,'refusal':3}
    reports={r['rcept_no']:r for r in read(BASE/'acquisition.json')['reports']}
    from src.processing.financial_parser import _sanitize_xml_like_text
    from src.storage.report_scope_filter import report_scope_filter
    trees={};catalogs={}
    for rid,r in reports.items():
        assert sha(r['source_file'])==r['xml_sha256']
        clean,_=_sanitize_xml_like_text(Path(r['source_file']).read_text('utf-8-sig'))
        trees[rid]=etree.ElementTree(etree.fromstring(clean.encode('utf8'),etree.XMLParser(no_network=True,resolve_entities=False,recover=False,huge_tree=True)))
        catalogs[rid]=read(BASE/f'sources/{rid}/catalog.json')['blocks']
    witnesses=[];questions=[]
    for q in rows:
        rid=q['receipt'];assert rid in reports
        q['report_scope']={'rcept_no':rid}
        assert report_scope_filter(q['report_scope'])=={'rcept_no':rid}
        ids={e['id'] for e in q['evidence']};assert len(ids)==len(q['evidence'])
        assert q['required_facts'] and q['reference_answer'].strip()
        for f in q['required_facts']:assert f['evidence_ids'] and set(f['evidence_ids'])<=ids
        for e in q['evidence']:
            nodes=trees[rid].xpath(e['xpath']);assert len(nodes)==1,(q['case_id'],e['id'],'xpath')
            literal=re.sub(r'\s+',' ',''.join(nodes[0].itertext())).strip()
            assert e['quote'] in literal,(q['case_id'],e['id'],'quote')
            block=catalogs[rid][e['block_index']]
            assert e['xpath']==block['xpath'] or e['xpath'].startswith(block['xpath']+'/'),(q['case_id'],e['id'],'catalog block')
            witnesses.append({'case_id':q['case_id'],'evidence_id':e['id'],'source_sha256':reports[rid]['xml_sha256'],
              'xpath':e['xpath'],'quote':e['quote'],'normalized_node_sha256':hashlib.sha256(literal.encode('utf8')).hexdigest(),'status':'EXACT_WITNESS_MATCH'})
        questions.append({'case_id':q['case_id'],'question':q['question'],'report_scope':q['report_scope'],'receipt':rid,'company':q['company'],'year':2025})
    counts=Counter(q['receipt'] for q in rows);assert set(counts.values())=={6}
    # Explicit evaluator-only arithmetic audit; no application rule is introduced.
    by={q['case_id']:q for q in rows};calculations=[]
    with localcontext() as ctx:
        ctx.prec=60
        for cid in ('H03','H09','H15'):
            c=by[cid]['calculation'];vals=[Decimal(o['value']) for o in c['operands']]
            for operand in c['operands']:
                evidence=next(e for e in by[cid]['evidence'] if e['id']==operand['evidence_id'])
                assert operand['value'] in evidence['quote'].replace(',','').replace(' ','')
            if cid=='H03':
                result=vals[0]-vals[1];assert result==Decimal(c['exact_result'])==Decimal('465078')
                calculated={'difference_million_krw':str(result)}
            elif cid=='H09':
                diff=vals[0]-vals[1];rate=diff/vals[1]*100
                assert diff==Decimal(c['exact_result']['increase_million_krw'])==356763
                assert Fraction(diff)*100/Fraction(vals[1])==Fraction(c['exact_result']['growth_percent_exact_fraction'])
                assert rate.quantize(Decimal('.01'),rounding=ROUND_HALF_UP)==Decimal('15.35')
                calculated={'difference_million_krw':str(diff),'growth_percent':str(rate),'rounded_percent':'15.35'}
            else:
                ratio=vals[0]/vals[1]*100
                assert Fraction(vals[0])*100/Fraction(vals[1])==Fraction(c['exact_result'].split()[0])
                assert ratio.quantize(Decimal('.1'),rounding=ROUND_HALF_UP)==Decimal('23.9')
                calculated={'share_percent':str(ratio),'rounded_percent':'23.9'}
            calculations.append({'case_id':cid,'operands':c['operands'],'calculated':calculated,'status':'PASS'})
    write(BASE/'questions.json',questions)
    write(BASE/'rubric.json',{'version':'holdout18-v1','authorship':'Assistant-authored from raw reports before retrieval/model answers; not observed user logs or independent human gold.',
       'primary_answerable_ids':[q['case_id'] for q in rows if q['kind']!='refusal'],
       'refusal_ids':[q['case_id'] for q in rows if q['kind']=='refusal'],
       'common_grading':read(BASE/'protocol.json')['metrics'],'cases':rows})
    write(BASE/'source_witness_validation.json',{'status':'PASS','witness_count':len(witnesses),'witnesses':witnesses,
       'limit':'Unique XPath and literal membership verify physical source linkage, not full semantic correctness. Gold reviewed separately. No generated answer or retrieval measured.'})
    write(BASE/'calculation_validation.json',{'status':'PASS','cases':calculations})
    write(BASE/'schedule.json',[{'ordinal':idx+1,'case_id':cid,'arm':arm,'repeat':rep}
       for idx,(cid,arm,rep) in enumerate((q['case_id'],arm,rep) for rep in (1,2) for i,q in enumerate(questions)
           for arm in (('A','C') if ((i+rep)%2==1) else ('C','A')))])
    print(json.dumps({'questions':len(rows),'types':dict(Counter(q['kind'] for q in rows)),'witnesses':len(witnesses),'arithmetic_checks':len(calculations)},ensure_ascii=False))
if __name__=='__main__':
    with offline():main()
