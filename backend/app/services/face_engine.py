import base64
import asyncio
import cv2
import httpx
import numpy as np
from fastapi import HTTPException
from gradio_client import Client
from ..config import get_settings


def _decode_image(image_base64: str) -> np.ndarray:
    clean = image_base64.split(",", 1)[-1]
    data = np.frombuffer(base64.b64decode(clean), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=422, detail="Invalid image")
    return image


def crop_face_base64(image_base64: str, face_box: list[int] | None) -> str:
    image = _decode_image(image_base64)
    if not face_box or len(face_box) != 4:
        return image_base64.split(",", 1)[-1]
    left, top, third, fourth = [int(value) for value in face_box]
    width = third - left if third > left else third
    height = fourth - top if fourth > top else fourth
    pad = int(max(width, height) * 0.18)
    x1 = max(0, left - pad)
    y1 = max(0, top - pad)
    x2 = min(image.shape[1], left + width + pad)
    y2 = min(image.shape[0], top + height + pad)
    cropped = image[y1:y2, x1:x2]
    if cropped.size == 0:
        return image_base64.split(",", 1)[-1]
    ok, buffer = cv2.imencode(".jpg", cropped, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
    if not ok:
        return image_base64.split(",", 1)[-1]
    return base64.b64encode(buffer).decode("ascii")


def _opencv_embedding(image_base64: str) -> dict:
    image = _decode_image(image_base64)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    face = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    vector = face.flatten()
    norm = np.linalg.norm(vector) or 1.0
    embedding = (vector / norm).tolist()
    return {
        "embedding": embedding,
        "face_box": [0, 0, int(image.shape[1]), int(image.shape[0])],
        "quality": {"engine": "opencv-fallback", "usable": True},
        "model": "opencv-fallback"
    }


async def create_embedding(image_base64: str) -> dict:
    settings = get_settings()
    if settings.face_engine == "huggingface":
        if not settings.hf_face_api_url:
            raise HTTPException(status_code=503, detail="Face service is waking up, please scan again in a few seconds.")
        fastapi_error = None
        try:
            async with httpx.AsyncClient(timeout=settings.hf_timeout_seconds) as client:
                response = await client.post(
                    f"{settings.hf_face_api_url.rstrip('/')}/embed",
                    headers={"Authorization": f"Bearer {settings.hf_face_api_token}"},
                    json={"image_base64": image_base64, "model": settings.hf_face_model}
                )
            if response.status_code >= 500:
                raise HTTPException(status_code=503, detail="Face service is waking up, please scan again in a few seconds.")
            if response.status_code >= 400:
                fastapi_error = HTTPException(status_code=response.status_code, detail=response.json().get("detail", "Face could not be processed"))
            else:
                return response.json()["data"]
        except httpx.HTTPError as error:
            fastapi_error = error
        try:
            return await _gradio_embedding(image_base64, settings)
        except Exception:
            if isinstance(fastapi_error, HTTPException):
                raise fastapi_error
            raise HTTPException(status_code=503, detail="Face service is waking up, please scan again in a few seconds.")
    return _opencv_embedding(image_base64)


async def create_embeddings(frames: list[str]) -> list[dict]:
    settings = get_settings()
    if settings.face_engine != "huggingface":
        return [_opencv_embedding(frame) for frame in frames]
    try:
        return await _gradio_embeddings(frames, settings)
    except Exception:
        return [await create_embedding(frame) for frame in frames]


async def _gradio_embedding(image_base64: str, settings) -> dict:
    def call():
        client = Client(settings.hf_face_api_url, verbose=False)
        result = client.predict(image_base64, settings.hf_face_api_token, settings.hf_face_model, api_name="/embed")
        if not isinstance(result, dict) or not result.get("success"):
            detail = result.get("detail", "Face could not be processed") if isinstance(result, dict) else "Face could not be processed"
            status_code = result.get("status_code", 422) if isinstance(result, dict) else 422
            raise HTTPException(status_code=status_code, detail=detail)
        return result["data"]

    return await asyncio.to_thread(call)


async def _gradio_embeddings(frames: list[str], settings) -> list[dict]:
    def call():
        client = Client(settings.hf_face_api_url, verbose=False)
        result = client.predict(frames, settings.hf_face_api_token, settings.hf_face_model, api_name="/embed_many")
        if not isinstance(result, dict) or not result.get("success"):
            detail = result.get("detail", "Faces could not be processed") if isinstance(result, dict) else "Faces could not be processed"
            status_code = result.get("status_code", 422) if isinstance(result, dict) else 422
            raise HTTPException(status_code=status_code, detail=detail)
        return result["data"]

    return await asyncio.to_thread(call)


def cosine_similarity(left: list[float], right: list[float]) -> float:
    a = np.array(left, dtype=np.float32)
    b = np.array(right, dtype=np.float32)
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1.0
    return float(np.dot(a, b) / denom)


def best_match(embedding: list[float], employees: list[dict]) -> dict:
    settings = get_settings()
    scored_by_employee = {}
    for employee in employees:
        vectors = employee.get("face_embeddings") or []
        if employee.get("face_embedding"):
            vectors.append(employee["face_embedding"])
        for vector in vectors:
            score = cosine_similarity(embedding, vector)
            employee_id = employee["employee_id"]
            current = scored_by_employee.get(employee_id)
            if not current or score > current["score"]:
                scored_by_employee[employee_id] = {"employee": employee, "score": score}
    scored = sorted(scored_by_employee.values(), key=lambda item: item["score"], reverse=True)
    if not scored or scored[0]["score"] < settings.face_match_threshold:
        raise HTTPException(status_code=422, detail="Face not recognized. Please scan again.")
    second = scored[1]["score"] if len(scored) > 1 else -1
    if scored[0]["score"] - second < settings.face_match_margin:
        raise HTTPException(status_code=422, detail="Face match is uncertain. Please scan again in better light.")
    return {"employee": scored[0]["employee"], "score": scored[0]["score"], "second_score": second}
