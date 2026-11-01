"""Frozen two-arm tokenizer diagnostic. Ignored artifact, not runtime code."""
from __future__ import annotations

import gzip
import importlib.metadata
import importlib.util
import json
import os
import re
import sys
import threading
import time
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
PREV = OUT.parent / 'table_schema_search_validated_offline_20261022'
HELPER = OUT.parent / 'table_row_search_offline_20261022/run.py'
sys.path.insert(0, str(OUT / '_deps'))
spec = importlib.util.spec_from_file_location('frozen_offline_helpers', HELPER)
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)  # Blocks socket connections and DNS before model import.
ARMS = ('A12', 'K12')
START = time.monotonic()
SEGMENT = re.compile(r'[가-힣]+|[a-zA-Z0-9]+')
HANGUL = re.compile(r'[가-힣]+')


def save(name, obj):
    p = (OUT / name).resolve()
    assert p.is_relative_to(OUT)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def heartbeat(phase, **kw):
    r = dict(phase=phase, elapsed_seconds=round(time.monotonic()-START, 2), pid=os.getpid(), **kw)
    with (OUT / 'heartbeat.jsonl').open('a', encoding='utf-8') as f:
        f.write(prior.encoded(r) + '\n')
    print(prior.encoded(r), flush=True)


def protect():
    paths = set(prior.protect()) | set(prior.load(PREV / 'before.json'))
    paths.update(str(p.relative_to(ROOT)) for p in PREV.rglob('*') if p.is_file())
    paths.update(['.venv/pyvenv.cfg', 'src/storage/bm25_index.py', 'src/storage/search_merge.py'])
    return {p: prior.sha(ROOT / p) for p in sorted(paths) if (ROOT / p).is_file()}


def preserve():
    before = prior.load(OUT / 'before.json')
    changed = [p for p, h in before.items() if not (ROOT/p).is_file() or prior.sha(ROOT/p) != h]
    r = dict(protected_files=len(before), changed=changed, unchanged=not changed)
    save('preservation.json', r)
    assert not changed, changed
    return r


def prepare():
    assert not (OUT / 'protocol.json').exists(), 'Protocol already frozen'
    old = prior.load(PREV / 'protocol.json')
    save('before.json', protect())
    protocol = {
        'status': 'FROZEN_BEFORE_TREATMENT_SCORING', 'date': '2026-10-22',
        'origin_skill': 'experiment-agent', 'mode': 'run', 'verification_status': 'UNVERIFIED',
        'hypothesis': 'Replacing Hangul character bigrams with morphological tokens reduces accidental partial matches and improves required-evidence coverage without losing existing evidence.',
        'cases': old['cases'], 'source_context_fields': old['source_context_fields'],
        'arms': {'A12': 'Current Korean character bigrams; original chunks.',
                 'K12': 'Same original chunks; each maximal Hangul segment analyzed by pinned Kiwi; all token forms retained.'},
        'tokenization': {'segment_regex': SEGMENT.pattern, 'kiwipiepy': '0.24.1', 'kiwipiepy_model': '0.24.0',
            'model_type': 'cong', 'num_workers': 1, 'integrate_allomorph': True, 'typos': None,
            'rules': 'Same maximal Hangul/ASCII segment extraction as baseline. Replace Hangul bigrams with Kiwi token.form values; retain all POS, including particles/endings. ASCII segments stay lowercase and numbers keep identical lexical splitting. No stopwords, user dictionary, aliases, typo correction, query expansion or benchmark rules. Analyze unique Hangul segments once with a shared query/corpus cache; no sentence-context analysis.'},
        'fixed': {'dense': 'Exact saved Dense16, no embeddings', 'lexical_limit': 24,
            'bm25': 'rank_bm25.BM25Okapi unchanged defaults; fit full 16051-chunk corpus independently per vocabulary',
            'scope': 'Original explicit report receipt; no query-derived filter', 'rrf': 'Same equal-weight RRF60 and tie ordering',
            'packet': 'Final12 original whole chunks, same metadata, 65536 UTF-8 bytes; no refill, compression or caption attachment',
            'schema_search': False, 'answer_generation': False},
        'targets_not_ranking_features': old['targets_not_ranking_features'],
        'evaluation': 'Frozen10-answerable/26-unit panel plus2 refusal controls, all77 source/citation/byte audit. Inspect alternatives for missing known witnesses. Full77 answer correctness and refusal performance are not measured.',
        'success_gate': 'Must preserve all baseline packet-covered required units and recover at least one previously missing unit; review historical citation losses for regressions. No adoption without new-report and answer validation.',
        'stop': 'One fixed Kiwi policy; no score-driven dictionary/POS/stopword tuning or additional variants.',
        'limits': {'external_model_api_calls': 0, 'external_model_cost_usd': 0, 'answers': 0, 'retrieval_seconds': 1800},
        'limitations': 'Development-exposed77, source review by same assistant without blinding; segment morphology may hurt compounds/proper nouns and lacks sentence-level context; vocabulary changes also change IDF and length statistics. No pure segmentation-only attribution.',
    }
    save('protocol.json', protocol)
    inputs = [PREV/'protocol.json', PREV/'known_witness_panel.json', PREV/'results.json',
              prior.EVIDENCE, prior.REVIEW, HELPER, ROOT/'src/storage/bm25_index.py', ROOT/'src/storage/search_merge.py',
              OUT.parent/'full77_sol_top12_20261020/requests.json', OUT.parent/'full77_sol_top12_20261020/grades.jsonl', OUT/'test_contract.py']
    inputs += list(prior.EXPORT.glob('*.jsonl.gz')) + list((prior.BASE/'live/retrieval').glob('*.json'))
    save('seal.json', {'protocol_sha256': prior.sha(OUT/'protocol.json'), 'runner_sha256': prior.sha(Path(__file__)),
                       'inputs': {str(p.relative_to(ROOT)): prior.sha(p) for p in inputs}})
    heartbeat('prepared', cases=len(protocol['cases']), protected_files=len(prior.load(OUT/'before.json')))


class MorphTokenizer:
    def __init__(self):
        from kiwipiepy import Kiwi
        self.kiwi = Kiwi(num_workers=1, model_type='cong', integrate_allomorph=True, typos=None)
        self.cache = {}

    def fill(self, segments):
        missing = sorted(set(segments) - self.cache.keys())
        for i in range(0, len(missing), 1000):
            batch = missing[i:i+1000]
            analyses = list(self.kiwi.tokenize(batch, normalize_coda=False, split_complex=False, stopwords=None))
            assert len(analyses) == len(batch)
            for raw, tokens in zip(batch, analyses):
                forms = [t.form for t in tokens]
                assert forms and all(forms), raw
                self.cache[raw] = {'forms': forms, 'tags': [t.tag for t in tokens]}
            heartbeat('morphology_progress', complete=min(i+1000, len(missing)), total=len(missing))

    def __call__(self, text):
        tokens = []
        for s in SEGMENT.findall(text):
            tokens.extend(self.cache[s]['forms'] if HANGUL.fullmatch(s) else [s.lower()])
        return tokens


def load_documents(fields):
    documents = {}
    for p in sorted(prior.EXPORT.glob('*.jsonl.gz')):
        with gzip.open(p, 'rt', encoding='utf-8') as f:
            for line in f:
                r = json.loads(line)
                m, text = r['metadata'], r['text']
                uid = m['chunk_uid']
                assert uid not in documents and prior.text_sha(text) == r['text_sha256']
                documents[uid] = {'uid': uid, 'receipt': str(m['rcept_no']), 'text': text,
                    'metadata': {k:v for k,v in m.items() if k in set(fields)|{'chunk_uid','chunk_id','sub_chunk_idx'}}}
        heartbeat('sources_loaded', chunks=len(documents))
    ordered = sorted(documents, key=lambda u: (documents[u]['receipt'], int(documents[u]['metadata'].get('chunk_id',0)), int(documents[u]['metadata'].get('sub_chunk_idx',0)), u))
    assert len(ordered) == 16051
    for i, u in enumerate(ordered):
        documents[u]['order'] = i
    return documents, ordered


def contributions(index, query_tokens, doc_pos):
    import numpy as np
    out = []
    for term, multiplicity in Counter(query_tokens).items():
        f = index.doc_freqs[doc_pos].get(term, 0)
        if not f:
            continue
        value = (index.idf.get(term) or 0) * f*(index.k1+1)/(f+index.k1*(1-index.b+index.b*index.doc_len[doc_pos]/index.avgdl))*multiplicity
        out.append({'term':term, 'query_tf':multiplicity, 'document_tf':f, 'contribution':float(value)})
    assert np.isclose(sum(r['contribution'] for r in out), index.get_scores(query_tokens)[doc_pos], atol=1e-9)
    return sorted(out, key=lambda r:-r['contribution'])


def run():
    assert not (OUT/'started.json').exists(), 'No automatic repeated treatment'
    protocol, seal = prior.load(OUT/'protocol.json'), prior.load(OUT/'seal.json')
    assert prior.sha(OUT/'protocol.json') == seal['protocol_sha256']
    assert prior.sha(Path(__file__)) == seal['runner_sha256']
    for p,h in seal['inputs'].items():
        assert prior.sha(ROOT/p) == h, p
    for package, version in [('kiwipiepy','0.24.1'),('kiwipiepy_model','0.24.0')]:
        assert importlib.metadata.version(package) == version
    dep_files = {str(p.relative_to(OUT)): prior.sha(p) for p in (OUT/'_deps').rglob('*') if p.is_file()}
    save('dependency_manifest.json', {'files':dep_files, 'python':sys.version,
        'versions': {p:importlib.metadata.version(p) for p in ['kiwipiepy','kiwipiepy_model','rank_bm25','numpy']}})
    save('started.json', {'pid':os.getpid(), 'utc_epoch':time.time(), 'command':sys.argv})
    done = threading.Event()
    def watchdog():
        while not done.wait(30):
            heartbeat('process_alive')
            if time.monotonic()-START > 1800:
                save('failure.json', {'status':'TIMEOUT','seconds':1800})
                print('Hard timeout reached; terminating only this experiment process.', flush=True)
                os._exit(124)
    threading.Thread(target=watchdog, daemon=True).start()
    documents, ordered = load_documents(protocol['source_context_fields'])
    corpus = [documents[u]['text'].strip() for u in ordered]
    baseline_tokens = [prior.tokenize_ko(t) for t in corpus]
    aindex = prior.BM25Okapi(baseline_tokens)
    saved = {r['case_id']:json.loads(r['body']['input'][1]['content']) for r in prior.load(OUT.parent/'full77_sol_top12_20261020/requests.json')}
    frozen = {c['id']:prior.load(prior.BASE/'live/retrieval'/f"{c['id']}.json") for c in protocol['cases']}
    original_scores = {}
    for c in protocol['cases']:
        scores = aindex.get_scores(prior.tokenize_ko(c['question']))
        hits = prior.fold_scores(scores, ordered, documents, str(c['report_scope']['rcept_no']))
        expected = frozen[c['id']]['bm25']
        assert [h['uid'] for h in hits] == [h['metadata']['chunk_uid'] for h in expected], c['id']
        assert all(abs(x['score']-y['score']) < 1e-8 for x,y in zip(hits,expected)), c['id']
        ranking = prior.merge(frozen[c['id']]['dense'], hits, documents, 40)
        p,_ = prior.packet(c, ranking[:12], documents, protocol['source_context_fields'], {h['uid'] for h in hits})
        assert p == saved[c['id']], ('baseline packet mismatch', c['id'])
        original_scores[c['id']] = scores
    save('baseline_parity.json', {'cases':77, 'BM25_ranks_equal':True, 'BM25_scores_atol':1e-8, 'A12_saved_packets_exact':True})
    heartbeat('baseline_parity_passed', cases=77)
    morph = MorphTokenizer()
    segments = {s for text in corpus+[c['question'] for c in protocol['cases']] for s in HANGUL.findall(text)}
    morph.fill(segments)
    with gzip.open(OUT/'morphology_cache.json.gz', 'wt', encoding='utf-8') as f:
        json.dump(morph.cache, f, ensure_ascii=False)
    ktokens = [morph(t) for t in corpus]
    kindex = prior.BM25Okapi(ktokens)
    save('index_stats.json', {a:{'documents':len(ordered), 'avgdl':idx.avgdl, 'vocabulary':len(idx.idf), 'tokens':sum(idx.doc_len)} for a,idx in [('A12',aindex),('K12',kindex)]})
    heartbeat('indexes_ready', unique_hangul_segments=len(segments))
    results, explanation = [], []
    for n,c in enumerate(protocol['cases'],1):
        cid, receipt = c['id'], str(c['report_scope']['rcept_no'])
        qt = {'A12':prior.tokenize_ko(c['question']), 'K12':morph(c['question'])}
        scores = {'A12':original_scores[cid], 'K12':kindex.get_scores(qt['K12'])}
        dense = frozen[cid]['dense']
        streams, rankings, packets = {}, {}, {}
        for arm in ARMS:
            streams[arm] = prior.fold_scores(scores[arm], ordered, documents, receipt)
            rankings[arm] = prior.merge(dense, streams[arm], documents, 40)
            p, omitted = prior.packet(c, rankings[arm][:12], documents, protocol['source_context_fields'], {h['uid'] for h in streams[arm]})
            assert all(d['text'] in (documents[d['chunk_id']]['text'],documents[d['chunk_id']]['text'].strip()) for d in p['documents'])
            packets[arm] = {'uids':[d['chunk_id'] for d in p['documents']], 'bytes':len(prior.encoded(p).encode('utf-8')), 'omitted':omitted}
            save(f'packets/{cid}_{arm}.json', p)
        targets = [dict(t) for t in protocol['targets_not_ranking_features'] if t['case_id'] == cid]
        for target in targets:
            target['full_lexical_rank'] = {}
            for arm in ARMS:
                full = prior.fold_scores(scores[arm], ordered, documents, receipt, limit=len(ordered))
                target['full_lexical_rank'][arm] = next((i+1 for i,h in enumerate(full) if h['uid'] == target['uid']), None)
        probe_uids = set(h['uid'] for h in streams['A12'][:3]+streams['K12'][:3]) | {t['uid'] for t in targets}
        for uid in sorted(probe_uids):
            explanation.append({'case_id':cid, 'uid':uid, 'terms':{a:contributions(idx,qt[a],documents[uid]['order']) for a,idx in [('A12',aindex),('K12',kindex)]}})
        results.append({'case_id':cid, 'query':c['question'], 'query_tokens':qt, 'report_scope':c['report_scope'],
            'dense':[{'uid':h['metadata']['chunk_uid'],'score':h['score']} for h in dense],
            'lexical':streams, 'rrf':rankings, 'packets':packets, 'targets':targets})
        if n%10 == 0 or n == 77:
            heartbeat('retrieval_progress', complete=n, total=77)
    save('results.json', results)
    save('score_explanations.json', explanation)
    preservation = preserve()
    save('execution_result.json', {'status':'COMPLETE_REVIEW_PENDING','origin_skill':'experiment-agent','mode':'run',
        'verification_status':'PARTIAL: exact baseline, offline retrieval and preservation verified; no answer evaluation',
        'model_api_calls':0,'external_model_cost_usd':0,'answers_generated':0,'cases':77,
        'elapsed_seconds':round(time.monotonic()-START,2),'preservation':preservation,'exit_code':0})
    done.set()
    heartbeat('complete', cases=77)


if __name__ == '__main__':
    try:
        {'prepare':prepare,'run':run,'preserve':preserve}[sys.argv[1]]()
    except Exception as exc:
        save('failure.json', {'type':type(exc).__name__,'error':str(exc)})
        raise
