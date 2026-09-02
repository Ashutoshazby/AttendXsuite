import os
from typing import Any

import cv2
import numpy as np
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from pydantic import BaseModel

from face_core import FaceApiError, cosine, decode_base64_image, embed_image

app = FastAPI(title="AttendXsuite HF Face API")


class EmbedPayload(BaseModel):
    image_base64: str | None = None
    model: str | None = None


class MatchPayload(BaseModel):
    image_base64: str
    employees: list[dict[str, Any]]
    threshold: float = 0.48
    margin: float = 0.06


def require_token(authorization: str | None = Header(default=None)):
    expected = os.getenv("HF_FACE_API_TOKEN", "replace_with_secret_token")
    if authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="Invalid face API token")


@app.get("/health")
def health():
    return {"success": True, "message": "AttendXsuite HF face API running"}


@app.post("/embed", dependencies=[Depends(require_token)])
async def embed(payload: EmbedPayload | None = None, image: UploadFile | None = File(default=None)):
    model_name = (payload.model if payload else None) or os.getenv("HF_FACE_MODEL", "buffalo_s")
    if image:
        content = await image.read()
        frame = cv2.imdecode(np.frombuffer(content, np.uint8), cv2.IMREAD_COLOR)
    elif payload and payload.image_base64:
        frame = decode_base64_image(payload.image_base64)
    else:
        raise HTTPException(status_code=422, detail="Image is required")
    if frame is None:
        raise HTTPException(status_code=422, detail="Invalid image")
    try:
        return {"success": True, "data": embed_image(frame, model_name)}
    except FaceApiError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail)


@app.post("/match", dependencies=[Depends(require_token)])
async def match(payload: MatchPayload):
    model_name = os.getenv("HF_FACE_MODEL", "buffalo_s")
    scan = embed_image(decode_base64_image(payload.image_base64), model_name)["embedding"]
    scored = []
    for employee in payload.employees:
        for vector in employee.get("face_embeddings", []):
            scored.append({"employee_id": employee["employee_id"], "score": cosine(scan, vector)})
    scored.sort(key=lambda item: item["score"], reverse=True)
    if not scored:
        raise HTTPException(status_code=422, detail="No known employee embeddings")
    second = scored[1]["score"] if len(scored) > 1 else -1
    accepted = scored[0]["score"] >= payload.threshold and scored[0]["score"] - second >= payload.margin
    return {"success": True, "data": {"accepted": accepted, "best": scored[0], "second_score": second}}
