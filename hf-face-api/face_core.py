import base64
import os
from functools import lru_cache
from typing import Any

import cv2
import numpy as np


class FaceApiError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def require_api_token(token: str | None) -> None:
    expected = os.getenv("HF_FACE_API_TOKEN", "replace_with_secret_token")
    if token != expected:
        raise FaceApiError(401, "Invalid face API token")


def decode_base64_image(image_base64: str) -> np.ndarray:
    clean = image_base64.split(",", 1)[-1]
    image_bytes = base64.b64decode(clean)
    image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise FaceApiError(422, "Invalid image")
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
        raise FaceApiError(503, "InsightFace model is not ready. Please try again in a few seconds.")


def warmup_model(model_name: str | None = None) -> dict:
    model = model_name or os.getenv("HF_FACE_MODEL", "buffalo_s")
    get_face_app(model)
    return {"model": model, "ready": True}


def embed_image(image: np.ndarray, model_name: str) -> dict:
    face_app = get_face_app(model_name)
    if face_app:
        try:
            faces = face_app.get(image)
        except Exception as error:
            print(f"[AttendXsuite HF] InsightFace runtime failed: {error}")
            raise FaceApiError(503, "InsightFace failed while processing the photo. Please try again.")
        if len(faces) != 1:
            raise FaceApiError(422, "Exactly one clear face is required")
        face = faces[0]
        embedding = np.array(face.embedding, dtype=np.float32)
        embedding = embedding / (np.linalg.norm(embedding) or 1.0)
        box = [int(value) for value in face.bbox.tolist()]
        return {
            "embedding": embedding.tolist(),
            "face_box": box,
            "quality": {"det_score": float(face.det_score), "usable": True},
            "model": model_name,
        }


def embed_base64(image_base64: str, model_name: str | None = None) -> dict:
    return embed_image(decode_base64_image(image_base64), model_name or os.getenv("HF_FACE_MODEL", "buffalo_s"))


def embed_many_base64(frames: list[str], model_name: str | None = None) -> list[dict]:
    results = []
    errors = []
    for frame in frames:
        try:
            results.append(embed_base64(frame, model_name))
        except FaceApiError as error:
            errors.append(error.detail)
    if not results and errors:
        raise FaceApiError(422, errors[-1])
    return results


def cosine(left: list[float], right: list[float]) -> float:
    a = np.array(left, dtype=np.float32)
    b = np.array(right, dtype=np.float32)
    return float(np.dot(a, b) / ((np.linalg.norm(a) * np.linalg.norm(b)) or 1.0))


def match_base64(image_base64: str, employees: list[dict[str, Any]], threshold: float, margin: float) -> dict:
    scan = embed_base64(image_base64)["embedding"]
    scored = []
    for employee in employees:
        for vector in employee.get("face_embeddings", []):
            scored.append({"employee_id": employee["employee_id"], "score": cosine(scan, vector)})
    scored.sort(key=lambda item: item["score"], reverse=True)
    if not scored:
        raise FaceApiError(422, "No known employee embeddings")
    second = scored[1]["score"] if len(scored) > 1 else -1
    accepted = scored[0]["score"] >= threshold and scored[0]["score"] - second >= margin
    return {"accepted": accepted, "best": scored[0], "second_score": second}
