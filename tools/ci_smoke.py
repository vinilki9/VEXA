"""Synthetic admin authentication against ephemeral CI PostgreSQL only."""
import json
import os
import secrets
from urllib.request import Request, urlopen
from urllib.error import HTTPError

if os.environ.get('VEXA_CI_SMOKE') != '1':
    raise SystemExit('CI-only test. Never run this against production.')
from app.main import app  # register ORM models
from app.database import SessionLocal
from app.models import User
from app.organization_access_models import PlatformAdmin
from app.security import hash_password

username = 'ci-smoke-' + secrets.token_hex(8)
password = secrets.token_urlsafe(24)
with SessionLocal() as db:
    user = User(username=username, password_hash=hash_password(password), is_active=True)
    db.add(user)
    db.flush()
    db.add(PlatformAdmin(user_id=user.id, created_by_user_id=None))
    db.commit()

base = 'http://127.0.0.1:8000/api/v1/platform-admin/auth'
def login(pw):
    return json.load(urlopen(Request(base+'/login', data=json.dumps({'username':username,'password':pw}).encode(), headers={'Content-Type':'application/json'}), timeout=10))
try:
    login('wrong-password')
except HTTPError as e:
    assert e.code == 401
else:
    raise AssertionError('Invalid password accepted')
token = login(password)['access_token']
me = json.load(urlopen(Request(base+'/me', headers={'Authorization':'Bearer '+token}), timeout=10))
assert me['username'] == username
print('Synthetic admin login, wrong password rejection and /me passed.')
