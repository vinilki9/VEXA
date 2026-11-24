import importlib.util
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / 'tools' / 'integration_preflight.py'
spec = importlib.util.spec_from_file_location('vexa_preflight', MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def test_contracts_present():
    results = mod.check()
    codes = {r['code']: r for r in results}
    for code in ('CITIES', 'TARIFFS', 'PRICE_PREVIEW', 'ORDER_CREATE', 'ORDER_HISTORY',
                 'SMS_REQUEST', 'SMS_VERIFY', 'LEGAL_CATALOG'):
        assert codes[code]['status'] == 'PASS', codes[code]

def test_wrapper_absence_is_reported_not_hidden():
    results = mod.check()
    for row in (x for x in results if x['code']=='GRADLE_WRAPPER'):
        if row['status']=='BLOCKED':
            assert 'missing' in row['detail']
