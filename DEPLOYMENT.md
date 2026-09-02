# AttendXsuite Deployment Guide

This guide deploys AttendXsuite in four pieces:

```text
Hugging Face Gradio Space -> face embedding API
MongoDB Atlas       -> production database
Render              -> main FastAPI backend
Vercel              -> admin dashboard and phone PWA
```

## 1. Hugging Face Face API

1. Create a Hugging Face Space.
2. Choose **Gradio** as the Space SDK.
3. Name it something like:

```text
attendxsuite-face-api
```

4. In the Space settings, add a secret:

```text
HF_FACE_API_TOKEN=<make-a-long-secret-token>
HF_FACE_MODEL=buffalo_s
```

5. In GitHub repository settings, add these repository secrets:

```text
HF_TOKEN=<your-hugging-face-write-token>
HF_SPACE_ID=<your-hf-username>/attendxsuite-face-api
```

6. Open GitHub Actions and run **Deploy HF Gradio Face API**, or push to `main`.

The deployed Space URL will look like:

```text
https://<your-hf-username>-attendxsuite-face-api.hf.space
```

The backend calls its named Gradio API endpoint `/embed` through `gradio_client`.

## 2. MongoDB Atlas

1. Create a free/shared MongoDB Atlas cluster.
2. Create a database user with a strong password.
3. Allow network access from Render. For first deployment/testing, you can use:

```text
0.0.0.0/0
```

4. Copy the connection string and set the database name to `attendxsuite`.

It should look like:

```text
mongodb+srv://<user>:<password>@<cluster-host>/attendxsuite?retryWrites=true&w=majority
```

## 3. Render Backend

1. In Render, create a new **Web Service** from the GitHub repo.
2. Use these settings:

```text
Name: attendxsuite-backend
Runtime: Python
Build Command: cd backend && pip install -r requirements.txt
Start Command: cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

3. Add environment variables:

```text
ENVIRONMENT=production
PYTHON_VERSION=3.11.11
MONGODB_URI=<your-mongodb-atlas-uri>
MONGODB_DATABASE=attendxsuite
JWT_SECRET=<make-a-long-random-secret>
CLIENT_ORIGINS=<dashboard-url>,<pwa-url>
COMPANY_TIMEZONE=Asia/Kolkata
FACE_ENGINE=huggingface
HF_FACE_API_URL=https://<your-hf-username>-attendxsuite-face-api.hf.space
HF_FACE_API_TOKEN=<same-token-used-in-hf-space>
HF_FACE_MODEL=buffalo_s
HF_TIMEOUT_SECONDS=60
FACE_MATCH_THRESHOLD=0.48
FACE_MATCH_MARGIN=0.06
FACE_SCAN_FRAME_COUNT=5
FACE_SCAN_CONSENSUS=3
```

4. Deploy and test:

```text
https://<your-render-service>.onrender.com/health
```

## 4. Vercel Dashboard

1. Import the GitHub repo into Vercel.
2. Set **Root Directory** to:

```text
frontend
```

3. Add environment variable:

```text
VITE_API_URL=https://<your-render-service>.onrender.com
```

4. Deploy.

## 5. Vercel Phone PWA

1. Create another Vercel project from the same GitHub repo.
2. Set **Root Directory** to:

```text
pwa-kiosk
```

3. Add environment variable:

```text
VITE_API_URL=https://<your-render-service>.onrender.com
```

4. Deploy.

Phone camera requires HTTPS, so use the Vercel URL on mobile.

## 6. Final Render CORS Update

After both Vercel projects are deployed, copy their URLs and update Render:

```text
CLIENT_ORIGINS=https://<dashboard>.vercel.app,https://<pwa>.vercel.app
```

Then redeploy Render.

## 7. Test Flow

1. Open dashboard URL.
2. Create company/admin.
3. Create employee.
4. Register face.
5. Open PWA URL on phone.
6. Login with user/admin.
7. Scan face and confirm attendance.
8. Check dashboard attendance table.
