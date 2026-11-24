from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_legal_panel_installed_in_both_web_apps():
    for app in ('dispatcher', 'platform-admin'):
        panel = ROOT/app/'src/components/LegalDocumentsPanel.tsx'
        assert panel.exists()
        text = panel.read_text()
        for expected in ('/pending', '/history', '/accept', 'sha256', 'openDocument', 'Проекты документов'):
            assert expected in text

def test_dispatcher_wired_to_account_role():
    text=(ROOT/'dispatcher/src/main.tsx').read_text()
    assert 'role="dispatcher"' in text
    assert 'token={token}' in text

def test_platform_admin_wired_to_account_role():
    text=(ROOT/'platform-admin/src/App.tsx').read_text()
    assert 'role="admin"' in text
    assert 'token={token}' in text
