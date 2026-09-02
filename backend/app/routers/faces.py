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
    replace_existing: bool = False


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
    faces = await collect_valid_faces(images)
    if not faces:
        raise HTTPException(status_code=422, detail="No clear face found. Use bright light, keep one face centered, and capture again.")
    for face in faces:
        await ensure_unique_face(user["company_id"], payload.employee_id, face["face"]["embedding"], face["face"].get("model"))
    samples = []
    for face in faces:
        samples.append({
            "image_base64": crop_face_base64(face["image"], face["face"].get("face_box")),
            "face_box": face["face"].get("face_box"),
            "quality": face["face"].get("quality"),
            "model": face["face"].get("model"),
            "created_at": now_utc()
        })
    embeddings = [face["face"]["embedding"] for face in faces]
    updates = {"face_embedding": embeddings[-1], "face_registered_at": now_utc(), "updated_at": now_utc()}
    if payload.replace_existing:
        await get_db().employees.update_one(
            {"_id": employee["_id"]},
            {"$set": {**updates, "face_embeddings": embeddings[-5:], "face_samples": samples[-5:]}}
        )
    else:
        await get_db().employees.update_one(
            {"_id": employee["_id"]},
            {"$set": updates, "$push": {"face_embeddings": {"$each": embeddings, "$slice": -5}, "face_samples": {"$each": samples, "$slice": -5}}}
        )
    return {"success": True, "message": "Face registered", "data": {"employee_id": payload.employee_id, "registered_faces": len(samples), "model": faces[-1]["face"].get("model")}}


async def collect_valid_faces(images: list[str]) -> list[dict]:
    if len(images) > 1:
        try:
            faces = await create_embeddings(images)
            return [{"image": image, "face": face} for image, face in zip(images, faces) if face.get("embedding")]
        except HTTPException:
            pass
    valid = []
    errors = []
    for image in images:
        try:
            face = await create_embedding(image)
            valid.append({"image": image, "face": face})
        except HTTPException as error:
            errors.append(str(error.detail))
    if not valid and errors:
        raise HTTPException(status_code=422, detail=errors[-1])
    return valid
