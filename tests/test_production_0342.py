from pathlib import Path
import subprocess
import yaml

ROOT = Path(__file__).resolve().parents[1]
def read(path): return (ROOT / path).read_text()

def test_immutable_images_and_health():
    s = yaml.safe_load(read('infrastructure/compose.production.yml'))['services']
    assert s['api']['image'] == s['migrate']['image'] == s['dispatch_worker']['image']
    for k in ('api','dispatcher','platform_admin','vexa_map','dispatch_worker'):
        assert '${VEXA_IMAGE_TAG' in s[k]['image'] and s[k]['healthcheck']
    assert all(s[k].get('logging') for k in s)

def test_ci_builds_and_tests_before_transfer():
    steps = yaml.safe_load(read('.github/workflows/deploy.yml'))['jobs']['check-build-deploy']['steps']
    labels = [x.get('name','') for x in steps]
    assert labels.index('Backend tests') < labels.index('Build Docker images on GitHub runner') < labels.index('Fresh PostgreSQL migrations and service smoke test') < labels.index('Send tested images and deploy')
    assert 'docker save' in steps[labels.index('Send tested images and deploy')]['run']
    assert 'docker load' in steps[labels.index('Send tested images and deploy')]['run']

def test_deploy_backup_before_migration_no_local_build():
    s=read('tools/deploy_vps.sh')
    assert 'compose "$TARGET" build' not in s
    assert s.index('bash "$BASE/backup.sh"') < s.index('run --rm --no-deps migrate')
    assert '$before == "$after"' in s and 'down --volumes' not in s
    assert 'state/current' in read('infrastructure/vexa-backup.service')

def test_sms_and_secrets_private():
    s=yaml.safe_load(read('infrastructure/compose.production.yml'))['services']
    assert s['api']['environment']['SMS_AERO_API_KEY']=='${SMS_AERO_API_KEY:-}'
    assert s['api']['environment']['LEGAL_DISPATCH_ENFORCEMENT']=='true'
    assert set(k for k,v in s.items() if v.get('ports'))=={'gateway'}

def test_shell_syntax():
    for p in (ROOT/'tools').glob('*.sh'):
        subprocess.run(['bash','-n',str(p)],check=True)

def test_restore_targets_new_database():
    s=read('tools/restore_test.sh')
    assert 'vexa_restore_test_' in s and 'createdb' in s
    assert 'dropdb' not in s and 'pg_restore --exit-on-error' in s
