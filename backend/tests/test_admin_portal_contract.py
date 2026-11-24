"""Source contract smoke checks; runnable without a live database or JWT secrets.

These do not replace a browser login against a running local PostgreSQL.
"""
import ast
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]


def test_both_portals_use_relative_asset_paths():
    assert "base: './'" in (ROOT / "dispatcher/vite.config.ts").read_text()
    assert 'base: "./"' in (ROOT / "platform-admin/vite.config.ts").read_text()
    for folder, prefix in (("dispatcher", "/api/"), ("platform-admin", "/api/")):
        conf = (ROOT / folder / f"nginx-{folder}.conf").read_text()
        assert f"location {prefix}" in conf
        assert 'proxy_pass http://api:8000;' in conf


def test_admin_me_handler_returns_actual_identity():
    path = ROOT / "backend/app/platform_admin_auth.py"
    tree = ast.parse(path.read_text())
    func = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "platform_admin_me")
    assert any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'Depends'
               for node in ast.walk(func)), "Must require role-checked dependency"
    func.decorator_list = []
    ast.fix_missing_locations(func)
    class AdminResponse:
        def __init__(self, id, username):
            self.id, self.username = id, username
    namespace = {'User': object, 'Depends': lambda _: None,
                 'get_current_platform_admin': lambda: None,
                 'PlatformAdminMeResponse': AdminResponse}
    code = ast.fix_missing_locations(ast.Module(body=[func], type_ignores=[]))
    exec(compile(code, str(path), 'exec'), namespace)
    user = SimpleNamespace(id=uuid4(), username='test_admin')
    profile = namespace['platform_admin_me'](user)
    assert profile.id == user.id
    assert profile.username == 'test_admin'


def test_admin_session_validation_uses_its_auth_endpoint():
    src = (ROOT / 'platform-admin/src/App.tsx').read_text()
    assert 'fetch(`${API_BASE}/auth/me`' in src
    assert 'setAdmin({ username: profile.username })' in src
    assert 'fetch(`${API_BASE}/organizations`' not in src


def test_dispatcher_verifies_token_before_showing_workspace():
    src = (ROOT / 'dispatcher/src/main.tsx').read_text()
    assert "apiRequest('/api/v1/dispatch/auth/me', savedToken)" in src
    assert 'if (!token || !dispatcher)' in src
    assert 'void loadOrders(token)' in src


def test_token_roles_not_cross_accepted():
    security = (ROOT / 'backend/app/security.py').read_text()
    platform = (ROOT / 'backend/app/platform_admin_auth.py').read_text()
    assert 'if token_type != "dispatcher":' in security
    assert 'if payload.get("token_type") != "platform_admin":' in platform
