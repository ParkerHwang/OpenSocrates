"""Deterministic checker predicates with deliberate violations; no application mutation."""
import copy,json
from checks import historical_equal
from supplement import assert_rejected
results=[]
def test(name,fn):
    try:fn();results.append(dict(name=name,status='pass'))
    except Exception as e:results.append(dict(name=name,status='fail',detail=str(e)))
def reject(fn):
    try:fn()
    except AssertionError:return
    raise AssertionError('deliberate violation escaped checker')
q=dict(memberId='regular',start='2026-11-06',end='2026-11-09',lines=[dict(itemId='camera',quantity=1,deposit=5000)],deposit=5000,refunded=1000)
def money():
    changed=copy.deepcopy(q);changed['deposit']=4999;assert not historical_equal(q,changed)
def additive():assert historical_equal(q,dict(q,lateFeePerUnitDay=0))
def missing():reject(lambda:assert_rejected({'ok':True},b'old',b'new'))
def partial():reject(lambda:assert_rejected({'ok':False,'error':{'code':'VALIDATION'}},b'old',b'partial'))
test('wrong-money rejected',money);test('compatible-additive-zero accepted',additive);test('missing-date acceptance rejected',missing);test('rejection partial-write detected',partial)
for key in ('lines','refunded'):
    test(f'dropped historical {key} rejected',lambda k=key: __import__('builtins').exec('assert not historical_equal(q,{a:b for a,b in q.items() if a!=k})',globals(),{'k':k}))
print(json.dumps(results,indent=2));assert all(r['status']=='pass' for r in results)
