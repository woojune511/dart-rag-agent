from common_exec import *
import copy, socket, time
import httpx
from decimal import Decimal
from run import Guard,embedding_entry,generation_entry,MAX_CALLS,CAP,WALL,MODEL,EMODEL

def denied(*a,**kw):raise Stop('Tests cannot use network')
socket.create_connection=socket.getaddrinfo=socket.socket.connect=socket.socket.connect_ex=denied
checks=[]
TEST_ROOT=OUT/'mock_final'
def reject(name,fn):
    try:fn()
    except Stop:checks.append(name)
    else:raise AssertionError('Admitted '+name)
def fixture_entry():
    body=copy.deepcopy(load(PREP/'protocol.json')['fixed_generation'])
    body['input'][1]['content']=enc({'query':'fixture','documents':[{'source_id':'x'}],'report_scope':{}}).decode()
    e={'body':body,'body_sha256':hashlib.sha256(enc(body)).hexdigest(),'input_bound':len(enc(body))+4096}
    return generation_entry(e,{'case_id':'fixture','arm':'A','repeat':1})
def mock_data(entry):
    if entry['kind']!='answer':
        return {'model':EMODEL,'usage':{'prompt_tokens':2,'total_tokens':2},'data':[{'index':0,'embedding':[1.0]+[0.0]*3071}]}
    return {'model':MODEL,'status':'completed','service_tier':'default','reasoning':{'effort':'low'},
      'usage':{'input_tokens':100,'output_tokens':10,'total_tokens':110,'input_tokens_details':{'cached_tokens':10,'cache_write_tokens':80}},
      'output':[{'type':'message','content':[{'type':'output_text','text':enc({'answer':'fixture','cited_source_ids':['x'],'abstained':False}).decode()}]}]}
def main():
    e=fixture_entry();valid=lambda req:httpx.Response(200,json=mock_data(e),request=req)
    for name in ['endpoint','body','call_cap','kind_cap','cost_cap','wall_cap','duplicate','closed','unplanned','unsettled']:
        g=Guard(TEST_ROOT/name,{e['label']:e['body_sha256']});req=httpx.Request('POST','https://api.openai.com/v1/responses',content=enc(e['body']))
        if name=='endpoint':req=httpx.Request('POST','https://example.com',content=enc(e['body']))
        if name=='body':req=httpx.Request('POST','https://api.openai.com/v1/responses',content=b'{}')
        if name=='call_cap':g.calls=105
        if name=='kind_cap':g.counts['answer']=72
        if name=='cost_cap':g.cost=CAP
        if name=='wall_cap':g.started=time.monotonic()-WALL-1
        if name=='duplicate':g.labels.add(e['label'])
        if name=='closed':g.closed=True
        if name=='unplanned':g.manifest={}
        if name=='unsettled':g.unsettled=Decimal('1')
        reject(name,lambda:g.validate(req,e));need(g.calls==(105 if name=='call_cap' else 0),'Rejection dispatched')
    for name in ['http_error','missing_usage','model_drift','usage_over_bound','tier_drift','reasoning_drift']:
        g=Guard(TEST_ROOT/name,{e['label']:e['body_sha256']})
        def bad(req):
            raw=mock_data(e)
            if name=='missing_usage':raw.pop('usage')
            if name=='model_drift':raw['model']='unexpected'
            if name=='usage_over_bound':raw['usage']['input_tokens']=300000
            if name=='tier_drift':raw['service_tier']='priority'
            if name=='reasoning_drift':raw['reasoning']['effort']='high'
            return httpx.Response(503 if name=='http_error' else 200,json=raw,request=req)
        with httpx.Client(transport=httpx.MockTransport(bad)) as client:reject(name,lambda:g.send(client,e))
        need(g.calls==1 and g.closed and g.unsettled==Decimal(e['reserve']),'Failure lost reservation or retried')
    for name in ['dimension','index','nonfinite']:
        entry=embedding_entry('query','q',['fixture'],2);g=Guard(TEST_ROOT/name,{entry['label']:entry['body_sha256']})
        data=mock_data(entry)
        if name=='dimension':data['data'][0]['embedding']=[1.0]
        if name=='index':data['data'][0]['index']=1
        if name=='nonfinite':data['data'][0]['embedding'][0]=float('nan')
        reject(name,lambda:g.validate_response(data,entry))
    for name in ['malformed','incomplete','unknown_citation','missing_citation']:
        g=Guard(TEST_ROOT/name,{e['label']:e['body_sha256']})
        def invalid(req):
            data=mock_data(e);content=data['output'][0]['content'][0]
            if name=='malformed':content['text']='invalid json'
            if name=='incomplete':data['status']='incomplete'
            if name=='unknown_citation':content['text']=enc({'answer':'bad','cited_source_ids':['unknown'],'abstained':False}).decode()
            if name=='missing_citation':content['text']=enc({'answer':'bad','cited_source_ids':[],'abstained':False}).decode()
            return httpx.Response(200,json=data,request=req)
        with httpx.Client(transport=httpx.MockTransport(invalid)) as client:g.send(client,e)
        answer=json.loads((g.path/'answers.jsonl').read_text('utf8'))
        need(answer['structural_errors'] and g.calls==1 and not g.closed,'Invalid answer not retained as failure');checks.append(name)
    g=Guard(TEST_ROOT/'success',{e['label']:e['body_sha256']})
    with httpx.Client(transport=httpx.MockTransport(valid)) as client:g.send(client,e)
    need(g.calls==1 and g.completed==1 and g.cost==Decimal('.000321') and g.unsettled==0,'Cost settlement')
    checks.append('valid_settlement_and_cache_write_rate')
    put(OUT/'test_result_final.json',{'at':now(),'status':'PASS','checks':checks,'count':len(checks),'external_calls':0,
      'run_sha256':sha(OUT/'run.py'),'offline_stage_sha256':sha(OUT/'offline_stage.py'),'common_sha256':sha(OUT/'common_exec.py')})
    print('GUARD PASS',len(checks),'controls; external calls0',flush=True)
if __name__=='__main__':main()
