"""No-network controls for money/call/identity boundaries and failure retention."""
from common import *
from run import Guard,entries,MODEL,URL,CAP,WALL
from decimal import Decimal
import copy,socket,time,httpx

def deny(*a,**kw):raise Stop('Tests forbid real network')
socket.create_connection=socket.getaddrinfo=socket.socket.connect=socket.socket.connect_ex=deny
checks=[]
def rejects(name, fn):
    try:fn()
    except Stop:checks.append(name)
    else:raise AssertionError('Accepted invalid state '+name)
def fixture(e):
    sid=json.loads(e['body']['input'][1]['content'])['documents'][0]['source_id']
    return {'model':MODEL,'status':'completed','service_tier':'default','reasoning':{'effort':'low'},
            'usage':{'input_tokens':100,'output_tokens':10,'total_tokens':110,
                     'input_tokens_details':{'cached_tokens':10,'cache_write_tokens':80}},
            'output':[{'type':'message','content':[{'type':'output_text','text':enc({'answer':'fixture','abstained':False,'cited_source_ids':[sid]}).decode()}]}]}
def main():
    e=entries()[0];root=OUT/'mock'
    for name in ('wrong_endpoint','wrong_body','call_cap','cost_cap','wall_cap','duplicate','closed','unplanned','unsettled'):
        g=Guard(root/name,{e['label']:e['body_sha256']})
        r=httpx.Request('POST',URL,content=enc(e['body']))
        if name=='wrong_endpoint':r=httpx.Request('POST','https://example.com/',content=enc(e['body']))
        if name=='wrong_body':r=httpx.Request('POST',URL,content=b'{}')
        if name=='call_cap':g.calls=72
        if name=='cost_cap':g.cost=CAP
        if name=='wall_cap':g.started=time.monotonic()-WALL-1
        if name=='duplicate':g.labels.add(e['label'])
        if name=='closed':g.closed=True
        if name=='unplanned':g.manifest={}
        if name=='unsettled':g.unsettled=Decimal('.1')
        rejects(name,lambda:g.validate(r,e));need(g.calls==(72 if name=='call_cap' else 0),'Rejection dispatched')
    for name in ('http503','missing_usage','model_drift','tier_drift','effort_drift','input_overrun','unknown_cache_cost'):
        g=Guard(root/name,{e['label']:e['body_sha256']})
        def bad(req):
            raw=fixture(e)
            if name=='missing_usage':raw.pop('usage')
            if name=='model_drift':raw['model']='different'
            if name=='tier_drift':raw['service_tier']='priority'
            if name=='effort_drift':raw['reasoning']['effort']='high'
            if name=='input_overrun':
                raw['usage']['input_tokens']=e['input_bound']+1;raw['usage']['total_tokens']=e['input_bound']+11
            if name=='unknown_cache_cost':raw['usage']['input_tokens_details'].pop('cache_write_tokens')
            return httpx.Response(503 if name=='http503' else 200,json=raw,request=req)
        with httpx.Client(transport=httpx.MockTransport(bad)) as client:rejects(name,lambda:g.send(client,e))
        need(g.calls==1 and g.completed==0 and g.closed and g.unsettled==Decimal(e['reserve']),'Failure retried or lost liability')
    for name in ('bad_json_answer','unknown_citation','missing_citation','incomplete_answer'):
        g=Guard(root/name,{e['label']:e['body_sha256']})
        def malformed(req):
            raw=fixture(e);c=raw['output'][0]['content'][0]
            if name=='bad_json_answer':c['text']='invalid-json'
            if name=='unknown_citation':c['text']=enc({'answer':'fixture','abstained':False,'cited_source_ids':['invalid']}).decode()
            if name=='missing_citation':c['text']=enc({'answer':'fixture','abstained':False,'cited_source_ids':[]}).decode()
            if name=='incomplete_answer':raw['status']='incomplete'
            return httpx.Response(200,json=raw,request=req)
        with httpx.Client(transport=httpx.MockTransport(malformed)) as client:g.send(client,e)
        a=json.loads((g.path/'answers.jsonl').read_text('utf8'))
        need(a['structural_errors'] and g.calls==g.completed==1 and not g.unsettled,'Malformed output not retained')
        checks.append(name)
    g=Guard(root/'valid',{e['label']:e['body_sha256']})
    with httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(200,json=fixture(e),request=req))) as client:g.send(client,e)
    need(g.cost==Decimal('.000342') and g.completed==1 and not g.unsettled,'Terra price settlement')
    checks.append('Terra_cache_write_read_output_cost')
    put(OUT/'guard_tests.json',{'status':'PASS','checks':checks,'count':len(checks),'external_calls':0,
        'run_sha256':sha(OUT/'run.py'),'common_sha256':sha(OUT/'common.py'),'test_sha256':sha(__file__)})
    print('MOCK GUARDS PASS',len(checks),'real calls0',flush=True)
if __name__=='__main__':main()
