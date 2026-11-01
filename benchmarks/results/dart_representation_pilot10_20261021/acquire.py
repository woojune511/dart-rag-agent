"""Read two official public filings; allow DART only and never print credentials."""
from common import *
import io
import zipfile
import xml.etree.ElementTree as ET
import requests
from dotenv import dotenv_values

def main():
    lock=load(BASE/'selection_lock.json')
    assert sha(BASE/'question_seed.json')==lock['question_seed_sha256']
    key=dotenv_values(ROOT/'.env').get('DART_API_KEY') or os.environ.get('DART_API_KEY')
    if not key: raise SystemExit('DART_API_KEY unavailable; no source requests dispatched')
    receipt={'started_at_utc':now(),'selection_lock_sha256':sha(BASE/'selection_lock.json'),'requests':[],'reports':[],'model_calls':0,'embedding_calls':0}
    def get(endpoint,params):
        assert endpoint in ('corpCode.xml','list.json','document.xml')
        try:
            r=requests.get('https://opendart.fss.or.kr/api/'+endpoint,params={'crtfc_key':key,**params},timeout=45,allow_redirects=False)
        except requests.RequestException:
            raise RuntimeError('DART transport failed; URL and credentials withheld') from None
        receipt['requests'].append({'endpoint':endpoint,'params_without_key':params,'status_code':r.status_code,'bytes':len(r.content)})
        if r.status_code!=200: raise RuntimeError('DART HTTP '+str(r.status_code))
        return r.content
    try:
        with zipfile.ZipFile(io.BytesIO(get('corpCode.xml',{}))) as z:
            tree=ET.fromstring(z.read('CORPCODE.xml'))
        codes={e.findtext('corp_name'):{'corp_code':e.findtext('corp_code'),'stock_code':e.findtext('stock_code')} for e in tree.findall('list') if e.findtext('stock_code','').strip()}
        for company in lock['companies']:
            identity=codes.get(company)
            if not identity: raise RuntimeError('Exact listed company unavailable: '+company)
            params={'corp_code':identity['corp_code'],'bgn_de':'20260101','end_de':'20261021','pblntf_detail_ty':'A001','last_reprt_at':'Y','page_count':100,'page_no':1,'sort':'date','sort_mth':'desc'}
            listing=json.loads(get('list.json',params))
            assert listing.get('status')=='000' and listing.get('total_page',1)<=1
            write(BASE/'sources'/(company+'_filing_list.json'),listing)
            matches=[r for r in listing['list'] if '사업보고서' in r['report_nm'] and '2025.12' in r['report_nm']]
            if not matches: raise RuntimeError('No matching 2025 annual report: '+company)
            row=sorted(matches,key=lambda x:(x['rcept_dt'],x['rcept_no']),reverse=True)[0]
            folder=BASE/'sources'/row['rcept_no']
            folder.mkdir(parents=True)
            blob=get('document.xml',{'rcept_no':row['rcept_no']})
            with (folder/'original.zip').open('xb') as f: f.write(blob)
            with zipfile.ZipFile(io.BytesIO(blob)) as z:
                members=[n for n in z.namelist() if n.lower().endswith('.xml')]
                main=[n for n in members if Path(n).stem==row['rcept_no']]
                assert len(main)==1,'Ambiguous main document'
                raw=z.read(main[0])
            with (folder/'original.xml').open('xb') as f: f.write(raw)
            receipt['reports'].append({'company':company,**identity,**row,'year':2025,'source_file':str(folder/'original.xml'),'zip_sha256':sha(folder/'original.zip'),'xml_sha256':sha(folder/'original.xml'),'xml_bytes':len(raw),'zip_members':members,'public_url':'https://dart.fss.or.kr/dsaf001/main.do?rcpNo='+row['rcept_no']})
            print(company,row['rcept_no'],row['report_nm'],len(raw),flush=True)
        receipt['status']='COMPLETE_PUBLIC_SOURCE_ACQUISITION'
    except Exception as e:
        receipt['status']='STOPPED';receipt['error_type']=type(e).__name__
        raise
    finally:
        receipt['finished_at_utc']=now()
        write(BASE/'acquisition.json',receipt)

if __name__=='__main__': main()
