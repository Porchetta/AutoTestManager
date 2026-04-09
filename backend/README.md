# Backend Development

WSL development quick start:

```bash
cd /home/hyun/develope/AutoTestManager/backend
chmod +x dev-setup.sh run-dev.sh
./dev-setup.sh
./run-dev.sh
```

Default local URLs:
- API: `http://localhost:8000`
- Docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

Default seeded admin:
- `user_id`: `admin`
- `password`: `admin1234`

Useful notes:
- `.env` is created from `.env.example` on first setup.
- `dev-setup.sh` prefers `uv` on WSL, so it works even when system `python3 -m venv` is unavailable.
- SQLite DB and mock result files are stored under `backend/data/`.
- RTD / ezDFS test execution, raw download, and summary download are currently mock implementations.
