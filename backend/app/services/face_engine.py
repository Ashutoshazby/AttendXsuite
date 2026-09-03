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
    face_box = _detect_opencv_face(gray)
    x, y, width, height = face_box
    face_region = gray[y:y + height, x:x + width]
    if face_region.size == 0:
        face_region = gray
        face_box = [0, 0, int(image.shape[1]), int(image.shape[0])]
    face = cv2.resize(face_region, (40, 40), interpolation=cv2.INTER_AREA)
    face = cv2.equalizeHist(face).astype(np.float32) / 255.0
    face = (face - float(face.mean())) / (float(face.std()) + 1e-6)
    gradient_x = cv2.Sobel(face, cv2.CV_32F, 1, 0, ksize=3)
    gradient_y = cv2.Sobel(face, cv2.CV_32F, 0, 1, ksize=3)
    texture = cv2.resize(np.sqrt((gradient_x * gradient_x) + (gradient_y * gradient_y)), (20, 20), interpolation=cv2.INTER_AREA)
    vector = np.concatenate([face.flatten(), texture.flatten()])
    norm = np.linalg.norm(vector) or 1.0
    embedding = (vector / norm).tolist()
    return {
        "embedding": embedding,
        "face_box": face_box,
        "quality": {"engine": "opencv-fallback", "feature_version": 2, "usable": True},
        "model": "opencv-fallback"
    }


def _detect_opencv_face(gray: np.ndarray) -> list[int]:
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    detector = cv2.CascadeClassifier(cascade_path)
    faces = detector.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=4, minSize=(64, 64))
    if len(faces):
        x, y, width, height = max(faces, key=lambda item: item[2] * item[3])
    else:
        side = int(min(gray.shape[:2]) * 0.72)
        x = max(0, (gray.shape[1] - side) // 2)
        y = max(0, (gray.shape[0] - side) // 2)
        width = height = side
    pad = int(max(width, height) * 0.16)
    x1 = max(0, int(x) - pad)
    y1 = max(0, int(y) - pad)
    x2 = min(gray.shape[1], int(x + width) + pad)
    y2 = min(gray.shape[0], int(y + height) + pad)
    return [x1, y1, x2 - x1, y2 - y1]


def _fallback_embedding(image_base64: str, reason: str | None = None) -> dict:
    face = _opencv_embedding(image_base64)
    if reason:
        face["quality"] = {**face.get("quality", {}), "fallback_reason": reason[:240]}
    return face


async def create_embedding(image_base64: str) -> dict:
    settings = get_settings()
    if settings.face_engine == "huggingface":
        if not settings.hf_face_api_url:
            raise HTTPException(status_code=503, detail="Face recognition service is not configured.")
        try:
            return await _gradio_embedding(image_base64, settings)
        except HTTPException:
            raise
        except Exception as gradio_error:
            fastapi_error = gradio_error
        try:
            return await _fastapi_embedding(image_base64, settings)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=503, detail=f"Face recognition service is not ready: {fastapi_error}")
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
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"Face recognition service is not ready: {error}")


async def _gradio_embedding(image_base64: str, settings) -> dict:
    result = await _gradio_call("embed", [image_base64, settings.hf_face_api_token, settings.hf_face_model], settings)
    if not isinstance(result, dict) or not result.get("success"):
        detail = result.get("detail", "Face could not be processed") if isinstance(result, dict) else f"Face could not be processed: {result}"
        status_code = result.get("status_code", 422) if isinstance(result, dict) else 422
        raise HTTPException(status_code=status_code, detail=detail)
    return result["data"]


async def _gradio_embeddings(frames: list[str], settings) -> list[dict]:
    result = await _gradio_call("embed_many", [frames, settings.hf_face_api_token, settings.hf_face_model], settings)
    if not isinstance(result, dict) or not result.get("success"):
        detail = result.get("detail", "Faces could not be processed") if isinstance(result, dict) else f"Faces could not be processed: {result}"
        status_code = result.get("status_code", 422) if isinstance(result, dict) else 422
        raise HTTPException(status_code=status_code, detail=detail)
    return result["data"]


async def _gradio_call(endpoint: str, data: list, settings):
    base_url = settings.hf_face_api_url.rstrip("/")
    timeout = httpx.Timeout(settings.hf_timeout_seconds, connect=15)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(f"{base_url}/gradio_api/call/{endpoint}", json={"data": data})
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=_response_detail(response, "Face service endpoint not found"))
        event_id = response.json().get("event_id")
        if not event_id:
            raise HTTPException(status_code=503, detail="Face service did not start the request")
        result = await client.get(f"{base_url}/gradio_api/call/{endpoint}/{event_id}")
        if result.status_code >= 400:
            raise HTTPException(status_code=result.status_code, detail=_response_detail(result, "Face service result not found"))
    error_seen = False
    latest_data = None
    for line in result.text.splitlines():
        if line.startswith("event: error"):
            error_seen = True
        if line.startswith("data: "):
            latest_data = json.loads(line.removeprefix("data: "))
            if isinstance(latest_data, list) and latest_data and isinstance(latest_data[0], str):
                try:
                    latest_data[0] = json.loads(latest_data[0])
                except json.JSONDecodeError:
                    pass
            if not error_seen:
                return latest_data[0] if isinstance(latest_data, list) and latest_data else latest_data
    if error_seen:
        detail = _gradio_error_detail(latest_data)
        raise HTTPException(status_code=503, detail=detail)
    raise HTTPException(status_code=503, detail="Face service returned no result")


def _gradio_error_detail(data) -> str:
    if isinstance(data, list) and data:
        data = data[0]
    if isinstance(data, dict):
        return data.get("detail") or data.get("error") or "Face service failed while processing the photo"
    if isinstance(data, str) and data:
        return data[:500]
    return "Face service failed while processing the photo"


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
    fallback_mode = len(embedding) == 2000
    threshold = 0.64 if fallback_mode else settings.face_match_threshold
    margin = 0.12 if fallback_mode else settings.face_match_margin
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
    if not scored or scored[0]["score"] < threshold:
        raise HTTPException(status_code=422, detail="Face not recognized. Please scan again.")
    second = scored[1]["score"] if len(scored) > 1 else -1
    if scored[0]["score"] - second < margin:
        raise HTTPException(status_code=422, detail="Face match is uncertain. Please scan again in better light.")
    return {"employee": scored[0]["employee"], "score": scored[0]["score"], "second_score": second}
