# VEXA — целевые параметры сервера

- Platform: Ubuntu VPS (user-provided).
- VPS IPv4: `109.120.184.20`.
- Planned public API URL: `https://109.120.184.20`.
- Planned reverse proxy: Nginx.
- Planned application stack: FastAPI + PostgreSQL + Redis + Docker Compose.
- Backend internal port: `8000`, bound to `127.0.0.1` by Compose.
- PostgreSQL and Redis: internal Docker network only; do not publish their ports publicly.

This is a project-side target configuration only. No connection, reachability check, server inspection, installation, firewall/DNS/TLS change, or deployment has been performed. The HTTPS URL is not verified. Prefer a domain with a valid TLS certificate before production.

The current Backend is a demo starter and the Android Client API path/payload still needs contract alignment. Driver and Dispatcher are not yet fully API-integrated.
