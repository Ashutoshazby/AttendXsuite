---
title: AttendXsuite Face API
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# AttendXsuite Hugging Face Face API

Standalone Face API for Hugging Face Docker Spaces.

## Endpoints

- `GET /health`
- `POST /embed`
- `POST /match`

`/embed` and `/match` require:

```text
Authorization: Bearer <HF_FACE_API_TOKEN>
```

## Environment

```env
HF_FACE_API_TOKEN=replace_with_secret_token
HF_FACE_MODEL=buffalo_s
PORT=7860
```

Start with `buffalo_s` for lower CPU cost. Upgrade to `buffalo_l` later if accuracy needs it.

The service does not permanently store photos, passwords, users, or attendance data.
