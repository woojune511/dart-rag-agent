"""Only the explicitly authorized free DART endpoints; credentials never logged."""
from common import *
import io, os, zipfile, requests
from lxml import etree
from dotenv import dotenv_values
def main():
    assert not (BASE/'acquisition.json').exists(), 'No automatic repeat acquisition'
    lock=read(BASE/'selection_lock.json')
    key=dotenv_values(ROOT/'.env').get('DART_API_KEY') or os.environ.get('DART_API_KEY')
    if not key: raise RuntimeError('DART key unavailable; no request sent')
    receipt={'at':now(),'selection_sha256':sha(BASE/'selection_lock.json'),'requests':[],'reports':[],
             'model_api_calls':0,'embedding_api_calls':0,'judge_api_calls':0,'retries':0}
    def get(endpoint,params):
        assert endpoint in ('corpCode.xml','list.json','document.xml')
        assert len(receipt['requests']) < 7
        item={'endpoint':endpoint,'params_without_key':params,'status':'DISPATCHED'}
        receipt['requests'].append(item)
        write(BASE/'acquisition_progress.json',receipt)
        try: r=requests.get('https://opendart.fss.or.kr/api/'+endpoint,params={'crtfc_key':key,**params},timeout=45,allow_redirects=False)
        except requests.RequestException: raise RuntimeError('DART transport failed; credentials withheld') from None
        item.update(http_status=r.status_code,bytes=len(r.content),status='RETURNED')
        if r.status_code!=200: raise RuntimeError('DART HTTP error')
        return r.content
    try:
        blob=get('corpCode.xml',{})
        (BASE/'corp_codes.zip').write_bytes(blob)
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            tree=etree.fromstring(z.read('CORPCODE.xml'),etree.XMLParser(resolve_entities=False,no_network=True))
        codes={e.findtext('stock_code').strip():{'corp_name':e.findtext('corp_name'),'corp_code':e.findtext('corp_code'),'stock_code':e.findtext('stock_code').strip()} for e in tree.findall('list') if e.findtext('stock_code','').strip()}
        for selected in lock['companies']:
            identity=codes[selected['stock_code']]
            params={'corp_code':identity['corp_code'],'bgn_de':'20260101','end_de':'20261023','pblntf_detail_ty':'A001','last_reprt_at':'Y','page_count':100,'page_no':1,'sort':'date','sort_mth':'desc'}
            listing=json.loads(get('list.json',params))
            assert listing.get('status')=='000' and int(listing.get('total_page',1))<=1
            write(BASE/'sources'/(selected['stock_code']+'_filing_list.json'),listing)
            matches=[r for r in listing['list'] if '사업보고서' in r['report_nm'] and lock['period'] in r['report_nm']]
            assert matches, 'No matching annual report'
            row=sorted(matches,key=lambda x:(x['rcept_dt'],x['rcept_no']),reverse=True)[0]
            folder=BASE/'sources'/row['rcept_no'];folder.mkdir(parents=True,exist_ok=False)
            blob=get('document.xml',{'rcept_no':row['rcept_no']})
            (folder/'original.zip').write_bytes(blob)
            with zipfile.ZipFile(io.BytesIO(blob)) as z:
                members=[n for n in z.namelist() if n.lower().endswith('.xml')]
                main_members=[n for n in members if Path(n).stem==row['rcept_no']]
                assert len(main_members)==1, 'Ambiguous main report'
                raw=z.read(main_members[0])
            (folder/'original.xml').write_bytes(raw)
            report={'label':selected['label'],**identity,**row,'year':2025,'source_file':str(folder/'original.xml'),
                    'xml_sha256':sha(folder/'original.xml'),'xml_bytes':len(raw),'zip_sha256':sha(folder/'original.zip'),
                    'zip_members':members,'public_url':'https://dart.fss.or.kr/dsaf001/main.do?rcpNo='+row['rcept_no']}
            receipt['reports'].append(report)
            print(json.dumps({k:report[k] for k in ('label','corp_name','rcept_no','report_nm','xml_bytes')},ensure_ascii=False),flush=True)
        receipt['status']='COMPLETE_PUBLIC_SOURCE_ACQUISITION'
    except Exception as e:
        receipt.update(status='STOPPED',error_type=type(e).__name__)
        raise
    finally:
        receipt['finished_at']=now();write(BASE/'acquisition.json',receipt)
if __name__=='__main__': main()
