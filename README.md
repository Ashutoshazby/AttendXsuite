# AttendXsuite

AttendXsuite is a separate advanced/hybrid attendance system based on Attendify logic. It does not use or reset the existing Attendify database.

## Architecture

```text
frontend/      Admin dashboard, face registration, and dashboard attendance scanner
pwa-kiosk/     Mobile-first browser PWA scanner, currently on hold
backend/       FastAPI, MongoDB, auth, RBAC, employee, attendance, reports
hf-face-api/   Separate Hugging Face Gradio Space face embedding API
scripts/       Local start, stop, tunnel, and smoke-check scripts
```

## Local Start

```powershell
cd D:\attendify\Attendify\AttendXsuite
npm run install:all
npm start
```

Open:

```text
Dashboard: http://127.0.0.1:8061
Backend:   http://127.0.0.1:8070/health
```

## Attendance

For now, mark attendance from the dashboard:

1. Open `http://127.0.0.1:8061`.
2. Login or create a company.
3. Create employees.
4. Register faces from Face Registry.
5. Use Dashboard Kiosk to start camera, scan face, and confirm Login/Logout.

PWA is on hold. When it is needed again, phone browsers require HTTPS for camera access:

```powershell
npm run tunnel
```

Then use the PWA tunnel link.

## Face Engines

Main backend supports:

```env
FACE_ENGINE=opencv
FACE_ENGINE=huggingface
HF_FACE_API_URL=https://your-space.hf.space
HF_FACE_API_TOKEN=secret
HF_FACE_MODEL=buffalo_s
```

If the Hugging Face API is sleeping or fails, attendance is not recorded and the UI should ask the user to scan again after a few seconds.

## Security And Roles

- `admin`: employees, faces, users, dashboard, reports, settings
- `user`: attendance only
- Backend enforces roles on protected routes
- HF Face API requires bearer token
- HF API does not store photos, passwords, or app database data

## Safety

- Face samples stay in the main MongoDB.
- Existing Attendify data is untouched.
- Duplicate faces are blocked.
- Unknown and uncertain matches do not record attendance.
- Rapid repeated punches are blocked.
- Hospital shifts support day, night, flexible, or custom shift fields.

## Check

```powershell
npm run check
```

## Deployment

- Deploy `backend/` as FastAPI service.
- Deploy `frontend/` as a static Vite site.
- Deploy `pwa-kiosk/` later if the PWA scanner is enabled again.
- Deploy `hf-face-api/` as a Hugging Face Gradio Space.
- Put secrets only in backend/HF environment variables, never frontend.
