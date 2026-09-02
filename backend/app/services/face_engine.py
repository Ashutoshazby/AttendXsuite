import base64
import json
import cv2
import httpx
import numpy as np
from fastapi import HTTPException
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


def _fallback_embedding(image_base64: str, reason: str | None = None) -> dict:
    face = _opencv_embedding(image_base64)
    if reason:
        face["quality"] = {**face.get("quality", {}), "fallback_reason": reason[:240]}
    return face


async def create_embedding(image_base64: str) -> dict:
    settings = get_settings()
    if settings.face_engine == "huggingface":
        if not settings.hf_face_api_url:
            return _fallback_embedding(image_base64, "Hugging Face URL is not configured")
        try:
            return await _gradio_embedding(image_base64, settings)
        except HTTPException as error:
            return _fallback_embedding(image_base64, str(error.detail))
        except Exception as gradio_error:
            fastapi_error = gradio_error
        try:
            return await _fastapi_embedding(image_base64, settings)
        except HTTPException as error:
            return _fallback_embedding(image_base64, str(error.detail))
        except Exception:
            return _fallback_embedding(image_base64, f"Face service is not ready: {fastapi_error}")
    return _opencv_embedding(image_base64)


async def _fastapi_embedding(image_base64: str, settings) -> dict:
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
            raise HTTPException(status_code=response.status_code, detail=response.json().get("detail", "Face could not be processed"))
        return response.json()["data"]
    except httpx.HTTPError:
        raise HTTPException(status_code=503, detail="Face service is waking up, please scan again in a few seconds.")


async def create_embeddings(frames: list[str]) -> list[dict]:
    settings = get_settings()
    if settings.face_engine != "huggingface":
        return [_opencv_embedding(frame) for frame in frames]
    try:
        return await _gradio_embeddings(frames, settings)
    except Exception:
        return [_fallback_embedding(frame, "Batch face service failed") for frame in frames]


async def _gradio_embedding(image_base64: str, settings) -> dict:
    result = await _gradio_call("embed", {
        "image_base64": image_base64,
        "api_token": settings.hf_face_api_token,
        "model": settings.hf_face_model,
    }, settings)
    if not isinstance(result, dict) or not result.get("success"):
        detail = result.get("detail", "Face could not be processed") if isinstance(result, dict) else f"Face could not be processed: {result}"
        status_code = result.get("status_code", 422) if isinstance(result, dict) else 422
        raise HTTPException(status_code=status_code, detail=detail)
    return result["data"]


async def _gradio_embeddings(frames: list[str], settings) -> list[dict]:
    result = await _gradio_call("embed_many", {
        "frames": frames,
        "api_token": settings.hf_face_api_token,
        "model": settings.hf_face_model,
    }, settings)
    if not isinstance(result, dict) or not result.get("success"):
        detail = result.get("detail", "Faces could not be processed") if isinstance(result, dict) else f"Faces could not be processed: {result}"
        status_code = result.get("status_code", 422) if isinstance(result, dict) else 422
        raise HTTPException(status_code=status_code, detail=detail)
    return result["data"]


async def _gradio_call(endpoint: str, payload: dict, settings):
    base_url = settings.hf_face_api_url.rstrip("/")
    timeout = httpx.Timeout(settings.hf_timeout_seconds, connect=15)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(f"{base_url}/gradio_api/call/v2/{endpoint}", json=payload)
        if response.status_code == 404:
            response = await client.post(f"{base_url}/gradio_api/call/{endpoint}", json={"data": list(payload.values())})
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=_response_detail(response, "Face service endpoint not found"))
        event_id = response.json().get("event_id")
        if not event_id:
            raise HTTPException(status_code=503, detail="Face service did not start the request")
        result = await client.get(f"{base_url}/gradio_api/call/{endpoint}/{event_id}")
        if result.status_code >= 400:
            raise HTTPException(status_code=result.status_code, detail=_response_detail(result, "Face service result not found"))
    for line in result.text.splitlines():
        if line.startswith("event: error"):
            raise HTTPException(status_code=503, detail="Face service failed while processing the photo")
        if line.startswith("data: "):
            data = json.loads(line.removeprefix("data: "))
            if isinstance(data, list) and data and isinstance(data[0], str):
                try:
                    data[0] = json.loads(data[0])
                except json.JSONDecodeError:
                    pass
            return data[0] if isinstance(data, list) and data else data
    raise HTTPException(status_code=503, detail="Face service returned no result")


def _response_detail(response, fallback: str) -> str:
    try:
        body = response.json()
        return body.get("detail") or body.get("error") or fallback
    except Exception:
        return fallback


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        return -1.0
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
