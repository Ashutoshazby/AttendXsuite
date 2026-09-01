# AttendXsuite Brain

AttendXsuite is a separate upgraded attendance system. It must not delete, reset, or damage the old Attendify database, employees, attendance history, or face samples.

## Current Focus

PWA is on hold for now.

Attendance should work from the website dashboard itself using the Dashboard Kiosk section.

## Folder Structure

```text
AttendXsuite/
  backend/       FastAPI backend, auth, employees, faces, attendance, realtime events
  frontend/      React + Vite dashboard and dashboard attendance scanner
  hf-face-api/   Optional separate Hugging Face face API
  pwa-kiosk/     PWA scanner, currently on hold
  scripts/       Start, stop, tunnel, and system check scripts
  tools/         Project-local tools, including portable MongoDB
```

## Running Ports

```text
Dashboard: http://127.0.0.1:8061
Backend:   http://127.0.0.1:8070
MongoDB:   mongodb://127.0.0.1:27018/attendxsuite
```

## Start Commands

```powershell
cd D:\attendify\Attendify\AttendXsuite
npm run install:all
npm start
```

Stop:

```powershell
npm run stop
```

Check full flow:

```powershell
npm run check
```

## MongoDB

MongoDB runs on port `27018`.

Compass connection string:

```text
mongodb://127.0.0.1:27018/attendxsuite
```

Main collections:

```text
companies
users
employees
attendance
password_otps
```

The start script can run portable MongoDB from:

```text
tools/mongodb-win32-x86_64-windows-8.0.29/bin/mongod.exe
```

Mongo data is stored at:

```text
backend/mongo-data
```

## Attendance Flow

```text
Admin logs in
  -> creates employee
  -> registers employee face
  -> opens Dashboard Kiosk
  -> starts camera
  -> scans face
  -> backend compares face embedding
  -> dashboard asks to confirm Login or Logout
  -> backend saves attendance in MongoDB
  -> realtime event updates dashboard
```

## Time Rules

Attendance time must come from backend system time, not browser time.

Backend stores timestamps in UTC and dashboard displays them in IST using:

```text
Asia/Kolkata
```

Today attendance and summary also use IST day boundaries.

## Face Recognition Rules

Current local engine:

```env
FACE_ENGINE=opencv
FACE_SCAN_FRAME_COUNT=5
FACE_SCAN_CONSENSUS=3
FACE_MATCH_THRESHOLD=0.48
FACE_MATCH_MARGIN=0.06
```

Rules:

- Use registered employee face data only.
- Do not randomly select an employee.
- Unknown faces should not mark attendance.
- If match is uncertain or too close, ask to scan again.
- Prevent rapid duplicate punches.

## Important Backend APIs

```text
POST /auth/register-company
POST /auth/login
GET  /auth/users
POST /auth/users
DELETE /auth/users/{user_id}

GET  /employees/list
POST /employees/create
PUT  /employees/update/{employee_id}
DELETE /employees/delete/{employee_id}

POST /faces/register

POST /attendance/scan
POST /attendance/confirm
GET  /attendance/today
GET  /attendance/summary
GET  /attendance/events
```

## Dashboard Notes

Main dashboard includes:

- Overview stats
- Employee creation
- User management
- Face Registry
- Dashboard Kiosk attendance scanner
- Attendance Today table

Normal users should only use attendance-related flow.

Admin can create and delete users.

## Current Verified Check

The latest smoke check passed:

```text
backend: ok
auth: ok
employeeCreate: ok
faceRegister: ok
scan: login
attendanceConfirm: ok
today: 1
present_today: 1
```

## Do Not Touch

- Do not delete old Attendify data.
- Do not reset old face samples.
- Do not remove existing attendance history.
- Do not move PWA back into main flow unless asked.
- Keep code lean and easy to understand.
