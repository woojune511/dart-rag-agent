"""Read saved artifacts only. No model, retrieval, Chroma, or application imports."""
from pathlib import Path
from collections import Counter, defaultdict
import gzip
import hashlib
import json
import socket

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
RESULTS = ROOT / 'benchmarks/results'

def deny(*args, **kwargs):
    raise RuntimeError('Offline source audit: network prohibited')

socket.create_connection = socket.socket.connect = socket.socket.connect_ex = socket.getaddrinfo = deny

def load(path):
    return json.loads(Path(path).read_text('utf-8'))

def read_lines(path):
    return [json.loads(x) for x in Path(path).read_text('utf-8').splitlines() if x.strip()]

def save(name, value):
    path = OUT / name
    assert path.resolve().is_relative_to(OUT)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', 'utf-8')

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024), b''): h.update(block)
    return h.hexdigest()

def exported(only=None):
    for path in sorted((RESULTS/'v12_store_recovery_preparation_2026-10-17').glob('*.jsonl.gz')):
        with gzip.open(path, 'rt', encoding='utf-8') as stream:
            for line, raw in enumerate(stream,1):
                row=json.loads(raw)
                uid=row['metadata']['chunk_uid']
                if only is None or uid in only:
                    assert hashlib.sha256(row['text'].encode()).hexdigest()==row['text_sha256']
                    row['export_locator']={'file':str(path.relative_to(ROOT)), 'line':line}
                    yield uid,row

def main():
    canonical=load(RESULTS/'full77_sol_top12_20261020/historical_baseline_grades.json')
    refs={x['id']:x for x in load(RESULTS/'full77_sol_top12_20261020/reference_questions.json')}
    rows={x['case_id']:{'case_id':x['case_id'],'question':refs[x['case_id']]['query'],
          'group':x['new_group'],'saved_judgments':{'Sol8_rescored':x['new_grade']},
          'saved_findings':[]} for x in canonical}
    for run,arm in [('full77_sol_top12_20261020','Sol12'),('full77_auto_facets_review_20261021','facets12')]:
        for x in read_lines(RESULTS/run/'grades.jsonl'):
            assert x['group']==rows[x['case_id']]['group']
            rows[x['case_id']]['saved_judgments'][arm]={k:x.get(k) for k in ['correctness','completeness','support','note','cited_source_ids','execution_status']}
    review_specs=[
      ('tokenizer_nori_idf_offline_20261022/nori_source_review.json','items'),
      ('tokenizer_nori_idf_offline_20261022/root_source_review.json','rows'),
      ('nori_structural_tf_offline_20261022/source_review.json','cases'),
      ('table_schema_search_validated_offline_20261022/source_review.json','cases'),
    ]
    for rel,key in review_specs:
        for item in load(RESULTS/rel)[key]:
            cid=item['case_id']; finding=item.get('disposition',item.get('verdict',item.get('finding')))
            rows[cid]['saved_findings'].append({'artifact':rel,'arm':item.get('arm'),
              'finding':finding,'note':item.get('rationale',item.get('interpretation',item.get('note')))})
    old_rows=load(RESULTS/'table_row_search_offline_20261022/review.json')['historical_pass_citation_review']['source_review']
    for item in old_rows:
        rows[item['case_id']]['saved_findings'].append({'artifact':'table_row_search_offline_20261022/review.json',
           'arm':'row_B8','finding':item['finding'],'note':item.get('note')})
    for row in rows.values():
        row['historical_failure_or_support_issue']=any(
          (row['group']=='common_answerable' and any(v.get(k)!='PASS' for k in ['correctness','completeness','support']))
          or v.get('support') not in ['PASS',None] for v in row['saved_judgments'].values())
        row['detailed_review_queued']=row['historical_failure_or_support_issue'] or bool(row['saved_findings'])
    assert len(rows)==77==len(refs)
    save('case_inventory.json',list(rows.values()))
    dirs=['full77_sol_top12_20261020','full77_sol_top8_20261020','full77_auto_facets_review_20261021',
          'full77_auto_facets_completion_20261021','full77_auto_facets_20261021',
          'tokenizer_nori_idf_offline_20261022','nori_structural_tf_offline_20261022',
          'table_schema_search_validated_offline_20261022','table_row_search_offline_20261022',
          'table_row_fixed_stats_offline_20261022','v12_store_recovery_preparation_2026-10-17',
          'sol_remaining8_failure_analysis_20261020','query_decomposition_v2_20261020_132630']
    manifest={}
    for directory in dirs:
        for path in (RESULTS/directory).rglob('*'):
            if path.is_file() and path.suffix in {'.json','.jsonl','.gz','.md','.py'}:
                manifest[str(path.relative_to(ROOT))]={'sha256':sha(path),'bytes':path.stat().st_size}
    prep=load(RESULTS/'full77_v12_final_20261018/preparation.json')
    for x in prep['reports']:
        path=ROOT/x['path']; manifest[str(path.relative_to(ROOT))]={'sha256':sha(path),'bytes':path.stat().st_size}
    for path in (RESULTS/'full77_v12_final_20261018/original_text').glob('*.txt'):
        manifest[str(path.relative_to(ROOT))]={'sha256':sha(path),'bytes':path.stat().st_size}
    save('input_manifest.json',manifest)
    print(json.dumps({'cases':len(rows),'groups':dict(Counter(x['group'] for x in rows.values())),
      'saved_failure_or_support_issue':sum(x['historical_failure_or_support_issue'] for x in rows.values()),
      'review_queue':sum(x['detailed_review_queued'] for x in rows.values()),'input_files':len(manifest)},ensure_ascii=False))
    for row in rows.values():
        if row['detailed_review_queued']: print(row['case_id'],row['group'],row['historical_failure_or_support_issue'],len(row['saved_findings']))

if __name__=='__main__': main()
