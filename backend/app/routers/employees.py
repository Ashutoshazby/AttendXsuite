from fastapi import APIRouter, Depends, HTTPException
from pymongo import ReturnDocument
from pydantic import BaseModel, EmailStr
from ..database import get_db
from ..dependencies import require_role
from ..services.face_engine import cosine_similarity
from ..utils.timezone import now_utc

router = APIRouter(prefix="/employees", tags=["employees"])


class EmployeePayload(BaseModel):
    employee_id: str
    name: str
    department: str = "General"
    phone: str | None = None
    email: EmailStr | None = None
    salary: float | None = None
    monthly_salary: float | None = None
    overtime_hourly_rate: float | None = None
    working_days_per_week: int = 6
    standard_daily_hours: float = 8
    shift_type: str = "flexible"
    shift_start: str | None = None
    shift_end: str | None = None
    active: bool = True


async def ensure_unique_face(company_id: str, employee_id: str, embedding: list[float], model: str | None = None):
    if not embedding:
        return
    if model == "opencv-fallback":
        return
    async for employee in get_db().employees.find({"company_id": company_id, "employee_id": {"$ne": employee_id}, "face_embeddings": {"$exists": True}}):
        for known in employee.get("face_embeddings", []):
            if cosine_similarity(embedding, known) >= 0.985:
                raise HTTPException(status_code=409, detail=f"Face is already registered for {employee.get('name', employee['employee_id'])}")


@router.get("/list")
async def list_employees(user=Depends(require_role("admin"))):
    employees = await get_db().employees.find({"company_id": user["company_id"]}).sort("name", 1).to_list(200)
    for employee in employees:
        employee["_id"] = str(employee["_id"])
    return {"success": True, "data": employees}


@router.post("/create")
async def create_employee(payload: EmployeePayload, user=Depends(require_role("admin"))):
    doc = payload.model_dump()
    if doc.get("monthly_salary") is None and doc.get("salary") is not None:
        doc["monthly_salary"] = doc["salary"]
    if doc.get("salary") is None and doc.get("monthly_salary") is not None:
        doc["salary"] = doc["monthly_salary"]
    doc.update({"company_id": user["company_id"], "face_samples": [], "face_embeddings": [], "created_at": now_utc(), "updated_at": now_utc()})
    try:
        result = await get_db().employees.insert_one(doc)
    except Exception:
        raise HTTPException(status_code=409, detail="Employee ID already exists")
    doc["_id"] = str(result.inserted_id)
    return {"success": True, "data": doc}


@router.put("/update/{employee_id}")
async def update_employee(employee_id: str, payload: EmployeePayload, user=Depends(require_role("admin"))):
    updates = payload.model_dump()
    if updates.get("monthly_salary") is None and updates.get("salary") is not None:
        updates["monthly_salary"] = updates["salary"]
    if updates.get("salary") is None and updates.get("monthly_salary") is not None:
        updates["salary"] = updates["monthly_salary"]
    updates["updated_at"] = now_utc()
    result = await get_db().employees.find_one_and_update(
        {"company_id": user["company_id"], "employee_id": employee_id},
        {"$set": updates},
        return_document=ReturnDocument.AFTER
    )
    if not result:
        raise HTTPException(status_code=404, detail="Employee not found")
    result["_id"] = str(result["_id"])
    return {"success": True, "data": result}


@router.delete("/{employee_id}")
async def delete_employee(employee_id: str, user=Depends(require_role("admin"))):
    result = await get_db().employees.delete_one({"company_id": user["company_id"], "employee_id": employee_id})
    if not result.deleted_count:
        raise HTTPException(status_code=404, detail="Employee not found")
    return {"success": True, "message": "Employee deleted"}
