from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from ..database import get_db
from ..dependencies import require_role
from ..services.face_engine import create_embedding, crop_face_base64
from ..routers.employees import ensure_unique_face
from ..utils.timezone import now_utc

router = APIRouter(prefix="/faces", tags=["faces"])


class FaceRegisterPayload(BaseModel):
    employee_id: str
    image_base64: str


@router.post("/register")
async def register_face(payload: FaceRegisterPayload, user=Depends(require_role("admin"))):
    employee = await get_db().employees.find_one({"company_id": user["company_id"], "employee_id": payload.employee_id, "active": True})
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    face = await create_embedding(payload.image_base64)
    await ensure_unique_face(user["company_id"], payload.employee_id, face["embedding"])
    cropped_preview = crop_face_base64(payload.image_base64, face.get("face_box"))
    sample = {
        "image_base64": cropped_preview,
        "face_box": face.get("face_box"),
        "quality": face.get("quality"),
        "model": face.get("model"),
        "created_at": now_utc()
    }
    await get_db().employees.update_one(
        {"_id": employee["_id"]},
        {"$set": {"face_embedding": face["embedding"], "face_registered_at": now_utc(), "updated_at": now_utc()}, "$push": {"face_embeddings": {"$each": [face["embedding"]], "$slice": -5}, "face_samples": {"$each": [sample], "$slice": -5}}}
    )
    return {"success": True, "message": "Face registered", "data": {"employee_id": payload.employee_id, "face_box": face.get("face_box"), "model": face.get("model")}}
