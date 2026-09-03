---
title: AttendXsuite Face API
colorFrom: blue
colorTo: green
sdk: gradio
pinned: false
---

# AttendXsuite Hugging Face Face API

Standalone Face API for Hugging Face Gradio Spaces.

Runs on Hugging Face's free CPU hardware. Do not enable ZeroGPU for this Space; CPU avoids ZeroGPU quota limits while keeping InsightFace recognition.

## Endpoints

- `GET /health`
- `POST /embed`
- `POST /match`

For free Hugging Face Spaces, create a **Gradio** Space and use the named API endpoints:

- `/health`
- `/embed`
- `/match`

`/embed` and `/match` require:

```text
api_token=<HF_FACE_API_TOKEN>
```

## Environment

```env
HF_FACE_API_TOKEN=replace_with_secret_token
HF_FACE_MODEL=buffalo_s
PORT=7860
```

Start with `buffalo_s` for lower CPU cost. Upgrade to `buffalo_l` later if accuracy needs it and the free CPU runtime remains responsive enough.

The service does not permanently store photos, passwords, users, or attendance data.
