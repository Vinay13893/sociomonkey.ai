MVP Backend (Flask)

Quick start:

1. Create virtualenv and install deps

```powershell
cd mvp/backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

2. Run server

```powershell
python run.py
```

API endpoints:
- POST /api/auth/register
- POST /api/auth/login
- GET /api/auth/me
- GET /api/projects
- POST /api/projects
- PUT /api/projects/<id>
- GET /api/leads
- POST /api/leads
- PUT /api/leads/<id>

Notes: This is minimal MVP code. Replace `SECRET_KEY` and use a proper DB for production.
