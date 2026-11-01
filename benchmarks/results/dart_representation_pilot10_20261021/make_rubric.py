"""Pre-answer rubric, transcribed from the original annual statement tables."""
from common import *
from decimal import Decimal, ROUND_HALF_UP

DATA = {
    '농심': {'rcept_no':'20260311003892','revenue':3514315500097,'operating_profit':183933032197,'inventory':353314247728,'assets':3822122467403,'ppe_cash':67592589702,'intangible_cash':262618117,
           'ranges':{'income':[3249,3290],'inventory':[3029,3130],'capex':[3735,3831],'business':[931,1145]}},
    '삼성전기': {'rcept_no':'20260310003071','revenue':11314459238100,'operating_profit':913331178557,'inventory':2412996843057,'assets':14595895255468,'ppe_cash':1192112995578,'intangible_cash':54210548833,
           'ranges':{'income':[2898,2926],'inventory':[2686,2781],'capex':[3436,3505],'business':[2207,2216]}},
}
def ratio(a,b):return str((Decimal(a)/Decimal(b)*100).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))

def main():
    out=[];excerpts={}
    for q in load(BASE/'question_seed.json'):
        d=DATA[q['company']];path=BASE/'sources'/d['rcept_no']/'generic_text.txt';lines=path.read_text('utf-8').splitlines()
        raw=(path.parent/'original.xml').read_bytes()
        for k in ('revenue','operating_profit','inventory','assets','ppe_cash','intangible_cash'):
            assert f'{d[k]:,}'.encode() in raw, 'Transcription missing from original XML'
        row={**q,'source_receipt':d['rcept_no'],'scope':'2025 consolidated','required':[],'optional':[]}
        if q['kind']=='income':
            row['gold']={'revenue_krw':d['revenue'],'operating_profit_krw':d['operating_profit'],'margin_percent':ratio(d['operating_profit'],d['revenue'])}
            row['required']=['Correct revenue (not gross sales before discounts), operating profit, units and period','Correct operating margin to two decimals or equivalent precision']
        elif q['kind']=='inventory':
            row['gold']={'inventory_krw':d['inventory'],'assets_krw':d['assets'],'ratio_percent':ratio(d['inventory'],d['assets'])}
            row['required']=['Net carrying inventory and total assets as of 2025-12-31, consolidated, with units','Correct inventory/assets ratio to two decimals or equivalent precision']
        elif q['kind']=='capex':
            row['gold']={'ppe_cash_krw':d['ppe_cash'],'intangible_cash_krw':d['intangible_cash'],'sum_krw':d['ppe_cash']+d['intangible_cash']}
            row['required']=['Both acquisition cash payments from the consolidated 2025 cash-flow statement, positive expenditure amounts','Correct sum and monetary unit; additions in asset movement notes are not substitutes']
        elif q['kind']=='business':
            if q['company']=='농심':
                row['required']=['Food manufacturing/sales as principal business, covering noodles, snacks and beverages','At least one source-supported representative product/brand per noodles, snacks and beverages category']
                row['examples']={'noodles':['신라면','안성탕면','짜파게티'],'snacks':['새우깡','포테토칩','양파링'],'beverages':['백산수','카프리썬','웰치스']}
                row['optional']=['Other merchandise such as Kellogg/Chupa Chups','Hotel/other subsidiaries','Geographic reportable segments; do not require geographic taxonomy because query does not specify accounting segments','Segment revenue and shares']
                row['ambiguity_note']='The company presents food manufacturing/sales product categories and also geographic financial segments. Do not label food product categories as separate IFRS reportable segments. Accept grouped food-business description if required products are covered.'
            else:
                row['required']=['Component segment and passive components, e.g. MLCC/inductor/chip resistor','Package solution segment and semiconductor package substrates','Optical solution segment and camera modules']
                row['optional']=['Sales, shares, customers, applications, market trends; any supplied extras still require support']
        else:
            row['required']=['Abstained true and explicitly says supplied evidence does not establish sales for the single requested day','No invented daily sales or annual-average proxy presented as that day actual sales']
            row['optional']=['Supported annual figures as contrast clearly not answering the daily request']
            row['negative_scope']='Evidence-relative refusal control. No claim that a substring scan proves absence from all possible company documents.'
        if q['kind'] in d['ranges']:
            a,b=d['ranges'][q['kind']];row['source_text_lines']=[a,b]
            excerpts[q['id']]={'source_file':str(path),'original_xml_sha256':sha(path.parent/'original.xml'),'derived_text_sha256':sha(path),'line_start':a,'line_end':b,'text':'\n'.join(lines[a-1:b])}
        out.append(row)
    write(BASE/'gold_source_excerpts.json',excerpts)
    write(BASE/'rubric.json',{'created_at':now(),'authored_before_retrieval_and_any_provider_calls':True,'reviewer':'Same assistant; no independent blind judge',
        'numeric_policy':'Accept equivalent unit conversions and rounding consistent with the displayed precision; all requested components mandatory. Ratio tolerance 0.01 percentage point. Additional material errors invalidate full correctness.',
        'faithfulness_policy':'Score separately from correctness. All material claims must be supported by supplied evidence with compatible period, scope and units. Selected IDs only are insufficient. Pure evidence-relative refusal has no unsupported claim; negative controls reported separately.',
        'questions':out})
    print(json.dumps({q['id']:q.get('gold',q['required']) for q in out},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
