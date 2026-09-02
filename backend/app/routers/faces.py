from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from ..database import get_db
from ..dependencies import require_role
from ..services.face_engine import create_embedding, create_embeddings, crop_face_base64
from ..routers.employees import ensure_unique_face
from ..utils.timezone import now_utc

router = APIRouter(prefix="/faces", tags=["faces"])


class FaceRegisterPayload(BaseModel):
    employee_id: str
    image_base64: str | None = None
    images_base64: list[str] | None = None


@router.post("/register")
async def register_face(payload: FaceRegisterPayload, user=Depends(require_role("admin"))):
    employee = await get_db().employees.find_one({"company_id": user["company_id"], "employee_id": payload.employee_id, "active": True})
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    images = [image for image in (payload.images_base64 or []) if image]
    if payload.image_base64:
        images.append(payload.image_base64)
    images = images[:5]
    if not images:
        raise HTTPException(status_code=422, detail="Capture at least one face photo")
    faces = await create_embeddings(images) if len(images) > 1 else [await create_embedding(images[0])]
    for face in faces:
        await ensure_unique_face(user["company_id"], payload.employee_id, face["embedding"])
    samples = []
    for image, face in zip(images, faces):
        samples.append({
            "image_base64": crop_face_base64(image, face.get("face_box")),
            "face_box": face.get("face_box"),
            "quality": face.get("quality"),
            "model": face.get("model"),
            "created_at": now_utc()
        })
    embeddings = [face["embedding"] for face in faces]
    await get_db().employees.update_one(
        {"_id": employee["_id"]},
        {"$set": {"face_embedding": embeddings[-1], "face_registered_at": now_utc(), "updated_at": now_utc()}, "$push": {"face_embeddings": {"$each": embeddings, "$slice": -5}, "face_samples": {"$each": samples, "$slice": -5}}}
    )
    return {"success": True, "message": "Face registered", "data": {"employee_id": payload.employee_id, "registered_faces": len(samples), "model": faces[-1].get("model")}}
