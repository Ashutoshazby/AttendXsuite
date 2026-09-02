# AttendXsuite Backend

FastAPI backend for auth, RBAC, employees, face samples, face embeddings, attendance, reports, settings, and realtime events.

## Run

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8070 --reload
```

Default DB: `mongodb://127.0.0.1:27018/attendxsuite`
