"""Provider-free synthetic gates before any real ranking."""
import base64
from collections import Counter
from run import BASE, OUT, field_max, read_fields, tokenize, prior, save

def C(**kw):return Counter(kw)

def main():
    tests=[]
    def check(name,condition):
        assert condition,name
        tests.append(name)
    check('no_fields_unchanged',field_max([C(a=4),C(),C(),C(b=2)])==C(a=4,b=2))
    check('duplicate_fields_not_summed',field_max([C(a=4),C(a=2),C(a=3),C(a=1)])==C(a=5))
    check('within_body_multiplicity_kept',field_max([C(a=9),C(a=2),C(a=2),C()])==C(a=9))
    check('label_only_multiplicity_preserved',field_max([C(a=1),C(z=3),C(z=2),C(a=7)])==C(a=8,z=3))
    check('other_prefix_tf_kept',field_max([C(a=4),C(a=2),C(a=3),C(a=8)])==C(a=12))
    texts=[
      '[table_row_labels: 가상항목 2024]\n[table_value_labels: 가상항목 123]\n[키워드: 가상항목]\n\n가상항목 | 2024 | 123',
      '[table_row_labels: 😀 가상항목 XyZ 123]\n[table_value_labels: 가상항목 XyZ 123]\n\n😀 가상항목 | XyZ | 123',
      '[키워드: 표]\n\n[table_row_labels: 가상항목]\n가상항목',
      '가상항목 2024년 값을 알려 줘.',
      '[table_row_labels: 가상항목]\n[table_value_labels: 값라벨전용 789]\n\n가상항목 | 123',
    ]
    inp=OUT/'synthetic_input.tsv'
    inp.write_text(''.join(str(i)+'\t'+base64.b64encode(t.encode()).decode()+'\n' for i,t in enumerate(texts)),encoding='utf-8')
    tokenize(inp,OUT/'synthetic_fields.tsv',OUT/'synthetic_java.log')
    rows=list(read_fields(OUT/'synthetic_fields.tsv'))
    check('all_rows_counted',len(rows)==5)
    check('label_field_names_unchanged',rows[0][1][3]['table']==2 and rows[0][1][3]['labels']==2)
    check('numeric_offsets_and_unicode',all(rows[1][1][j]['xyz']==1 and rows[1][1][j]['123']==1 for j in (0,1,2)))
    check('numeric_duplicates_once',field_max(rows[1][1])['123']==1)
    check('body_like_field_is_not_prefix',rows[2][2]==0 and field_max(rows[2][1])==Counter(rows[2][0]))
    check('query_unchanged',rows[3][2]==0 and field_max(rows[3][1])==Counter(rows[3][0]))
    check('label_only_numeric_retained',field_max(rows[4][1])['789']==1)
    check('no_vocabulary_loss',all(Counter(full).keys()==field_max(zones).keys() for full,zones,_ in rows))
    check('fulltext_synthetic_network_denied','network_denial_verified' in (OUT/'synthetic_java.log').read_text())
    save('contract_result.json',{'passed':True,'tests':tests,'count':len(tests)})
    print('PASS',len(tests),'contracts')

if __name__=='__main__':main()
