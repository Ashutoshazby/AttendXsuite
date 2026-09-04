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

## Local Laptop Server Start

```powershell
cd D:\AttendXsuite
npm run install:all
npm start
```

Open:

```text
Dashboard on server laptop: http://127.0.0.1:8061
Backend on server laptop:   http://127.0.0.1:8070/health
Dashboard on other devices: http://<server-laptop-ip>:8061
```

`npm start` prints the detected LAN URL, for example `http://192.168.1.25:8061`. Use that URL from phones or other computers connected to the same Wi-Fi/LAN.

If you are running this on the same laptop as the HMS server at `192.168.1.14`, open:

```text
Attendance Dashboard: http://192.168.1.14:8061
Attendance Backend:   http://192.168.1.14:8070/health
```

The start script trusts `192.168.1.14` by default. To use a different fixed server IP, run PowerShell like this before `npm start`:

```powershell
$env:ATTENDX_SERVER_IP="192.168.1.14"
npm start
```

If another device cannot open the dashboard:

- Keep the server laptop awake and connected to the same network.
- Allow Windows Firewall access for Node.js and Python when prompted.
- If needed, manually allow inbound TCP ports `8061` and `8070`.
- Run `ipconfig` on the server laptop and use the IPv4 address shown for the active Wi-Fi/LAN adapter.

The local script uses `FACE_ENGINE=opencv`, so it does not depend on the Hugging Face hosted face API for normal local use. MongoDB runs through Docker on port `27018` when Docker is available; otherwise the backend falls back to a local JSON database.

Create a local backup any time with:

```powershell
npm run backup
```

For a 25-30 employee hospital setup, run this at least once daily and keep a copy on a pen drive or another computer.

## Attendance

For now, mark attendance from the dashboard:

1. Open `http://127.0.0.1:8061` on the server laptop, or `http://<server-laptop-ip>:8061` from another device on the same network.
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
