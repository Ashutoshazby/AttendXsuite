import base64
import os
from functools import lru_cache
from typing import Any

import cv2
import numpy as np
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from pydantic import BaseModel

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


def decode_base64_image(image_base64: str) -> np.ndarray:
    clean = image_base64.split(",", 1)[-1]
    image_bytes = base64.b64decode(clean)
    image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=422, detail="Invalid image")
    return image


@lru_cache
def get_face_app(model_name: str):
    try:
        from insightface.app import FaceAnalysis
        face_app = FaceAnalysis(name=model_name, providers=["CPUExecutionProvider"])
        face_app.prepare(ctx_id=-1, det_size=(320, 320))
        return face_app
    except Exception as error:
        print(f"[AttendXsuite HF] InsightFace unavailable: {error}")
        return None


def fallback_embedding(image: np.ndarray) -> list[float]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    vector = small.flatten()
    norm = np.linalg.norm(vector) or 1.0
    return (vector / norm).tolist()


def embed_image(image: np.ndarray, model_name: str) -> dict:
    face_app = get_face_app(model_name)
    if face_app:
        faces = face_app.get(image)
        if len(faces) != 1:
            raise HTTPException(status_code=422, detail="Exactly one clear face is required")
        face = faces[0]
        embedding = np.array(face.embedding, dtype=np.float32)
        embedding = embedding / (np.linalg.norm(embedding) or 1.0)
        box = [int(value) for value in face.bbox.tolist()]
        return {
            "embedding": embedding.tolist(),
            "face_box": box,
            "quality": {"det_score": float(face.det_score), "usable": True},
            "model": model_name
        }

    return {
        "embedding": fallback_embedding(image),
        "face_box": [0, 0, int(image.shape[1]), int(image.shape[0])],
        "quality": {"fallback": "opencv", "usable": True},
        "model": "opencv-fallback"
    }


def cosine(left: list[float], right: list[float]) -> float:
    a = np.array(left, dtype=np.float32)
    b = np.array(right, dtype=np.float32)
    return float(np.dot(a, b) / ((np.linalg.norm(a) * np.linalg.norm(b)) or 1.0))


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
    return {"success": True, "data": embed_image(frame, model_name)}


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
