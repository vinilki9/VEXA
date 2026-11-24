#!/usr/bin/env python3
"""Offline, standard-library-only integration checks for VEXA source checkout.
This is not a substitute for running services or Android builds.
"""
from pathlib import Path
import ast
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def check():
    findings = []
    def add(area, code, ok, detail):
        findings.append({"area": area, "code": code, "status": "PASS" if ok else "BLOCKED", "detail": detail})

    for app in ("client", "driver"):
        base = ROOT / "android" / app
        wrapper = base / "gradle" / "wrapper" / "gradle-wrapper.jar"
        add(app, "GRADLE_WRAPPER", wrapper.is_file(), f"{app}: gradle-wrapper.jar {'exists' if wrapper.is_file() else 'missing'}")
        add(app, "ANDROID_MANIFEST", (base / "app" / "src" / "main" / "AndroidManifest.xml").is_file(), "AndroidManifest.xml exists")
        add(app, "ANDROID_BUILD", (base / "app" / "build.gradle.kts").is_file(), "App Gradle config exists")

    app_main = (ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    api = (ROOT / "android" / "client" / "app" / "src" / "main" / "java" / "ru" / "vexa" / "client" / "ApiClient.kt").read_text(encoding="utf-8")
    da = (ROOT / "backend" / "app" / "driver_api.py").read_text(encoding="utf-8")
    pa = (ROOT / "backend" / "app" / "passenger_auth.py").read_text(encoding="utf-8")
    legal = (ROOT / "backend" / "app" / "legal_documents.py").read_text(encoding="utf-8")
    for code, mobile_path, backend_anchor in (
        ("CITIES", '/api/v1/cities', '@app.get("/api/v1/cities")'),
        ("TARIFFS", '/api/v1/tariffs/', '/api/v1/tariffs/{city_code}'),
        ("PRICE_PREVIEW", '/api/v1/orders/price-preview', '/api/v1/orders/price-preview'),
        ("ORDER_CREATE", '/api/v1/orders', '/api/v1/orders'),
        ("ORDER_HISTORY", '/api/v1/passenger/orders', '/api/v1/passenger/orders'),
    ):
        add('client-backend', code, mobile_path in api and backend_anchor in app_main, f'Mobile path and server route: {mobile_path}')
    for code, mobile_path, server_anchor in (
        ('SMS_REQUEST', '/api/v1/auth/passenger/request', '@router.post("/request")'),
        ('SMS_VERIFY', '/api/v1/auth/passenger/verify', '@router.post("/verify")'),
    ):
        add('client-auth', code, mobile_path in api and server_anchor in pa, mobile_path)
    add('legal', 'LEGAL_CATALOG', '/api/v1/legal/roles/' in api and '@router.get("/roles/{role}")' in legal,
        'Client reads role-specific legal catalog')
    for method in ('auth/login', 'me', 'online', 'location', 'orders/active', 'orders/offers', 'wallet'):
        path='/api/v1/driver/'+method
        add('driver-backend','DRIVER_'+method.upper().replace('/','_'), path in da, path)

    for name in ('dispatcher','platform-admin'):
        package = ROOT / name / 'package.json'
        add(name, 'WEB_BUILD_SCRIPT', package.is_file() and '"build"' in package.read_text(encoding='utf-8'),
            f'{name} build script present; execution not asserted')

    add('backend', 'DEPENDENCY_MANIFEST', (ROOT / 'backend' / 'requirements.txt').is_file(),
        'requirements.txt exists; dependencies are not necessarily installed')
    add('database', 'ALEMBIC_CONFIG', (ROOT / 'backend' / 'alembic.ini').is_file(), 'Alembic config exists; migration not executed')
    return findings


def main():
    findings = check()
    print(json.dumps({'source': 'local source inspection', 'findings': findings,
                      'counts': {'passed': sum(x['status']=='PASS' for x in findings),
                                 'blocked': sum(x['status']!='PASS' for x in findings)}},
                     ensure_ascii=False, indent=2))
    sys.exit(1 if any(x['status']!='PASS' for x in findings) else 0)

if __name__ == '__main__':
    main()
