import asyncio
from collections import Counter
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from ..config import get_settings
from ..database import get_db
from ..dependencies import current_user, require_role
from ..services.face_engine import best_match, create_embeddings
from ..services.realtime import publish, subscribe, sse
from ..utils.timezone import day_range_utc, local_date_key, now_utc

router = APIRouter(prefix="/attendance", tags=["attendance"])
PUNCH_GAP_SECONDS = 60


class ScanPayload(BaseModel):
    frames: list[str]
    device_id: str = "pwa-kiosk"
    timestamp: str | None = None


async def attendance_type(company_id: str, employee_id: str, timestamp):
    timezone = get_settings().company_timezone
    start, end = day_range_utc(local_date_key(timestamp, timezone), timezone)
    latest = await get_db().attendance.find({"company_id": company_id, "employee_id": employee_id, "timestamp": {"$gte": start, "$lte": end}}).sort("timestamp", -1).limit(1).to_list(1)
    return "logout" if latest and latest[0]["type"] == "login" else "login"


@router.get("/events")
async def events(token: str):
    from ..services.security import decode_token
    payload = decode_token(token)
    company_id = payload["company_id"]

    async def stream():
        async for queue in subscribe(company_id):
            yield sse("connected", {"success": True})
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=25)
                    yield sse(item["event"], item["data"])
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.post("/scan")
async def scan(payload: ScanPayload, user=Depends(require_role("admin", "user"))):
    settings = get_settings()
    frames = payload.frames[: settings.face_scan_frame_count]
    if not frames:
        raise HTTPException(status_code=422, detail="No scan frames received")
    employees = await get_db().employees.find({"company_id": user["company_id"], "active": True, "face_embeddings": {"$exists": True}}).to_list(100)
    votes = []
    faces = await create_embeddings(frames)
    for face in faces:
        match = best_match(face["embedding"], employees)
        votes.append(match["employee"]["employee_id"])
    winner, count = Counter(votes).most_common(1)[0]
    if count < settings.face_scan_consensus:
        raise HTTPException(status_code=422, detail="Face match is uncertain. Please scan again.")
    employee = await get_db().employees.find_one({"company_id": user["company_id"], "employee_id": winner})
    action = await attendance_type(user["company_id"], winner, now_utc())
    sample = (employee.get("face_samples") or [])[-1] if employee else {}
    return {"success": True, "data": {"employee_id": winner, "employee_name": employee["name"], "action": action, "face_preview": sample.get("image_base64", "")}}


class ConfirmPayload(BaseModel):
    employee_id: str
    action: str
    device_id: str = "pwa-kiosk"
    timestamp: str | None = None


@router.post("/confirm")
async def confirm(payload: ConfirmPayload, user=Depends(require_role("admin", "user"))):
    if payload.action not in {"login", "logout"}:
        raise HTTPException(status_code=422, detail="Invalid attendance action")
    timestamp = now_utc()
    last = await get_db().attendance.find({"company_id": user["company_id"], "employee_id": payload.employee_id}).sort("timestamp", -1).limit(1).to_list(1)
    if last and abs((timestamp - last[0]["timestamp"]).total_seconds()) < PUNCH_GAP_SECONDS:
        raise HTTPException(status_code=409, detail="Attendance already marked recently. Please wait.")
    employee = await get_db().employees.find_one({"company_id": user["company_id"], "employee_id": payload.employee_id, "active": True})
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    expected = await attendance_type(user["company_id"], payload.employee_id, timestamp)
    if expected != payload.action:
        payload.action = expected
    doc = {"company_id": user["company_id"], "employee_id": payload.employee_id, "type": payload.action, "device_id": payload.device_id, "timestamp": timestamp, "created_at": now_utc()}
    result = await get_db().attendance.insert_one(doc)
    doc["_id"] = str(result.inserted_id)
    doc["employee_name"] = employee["name"]
    await publish(user["company_id"], "attendance-updated", doc)
    return {"success": True, "message": f"{payload.action.title()} recorded", "data": doc}


@router.get("/today")
async def today(user=Depends(require_role("admin", "user"))):
    timezone = get_settings().company_timezone
    start, end = day_range_utc(tz=timezone)
    employees = await get_db().employees.find({"company_id": user["company_id"]}).to_list(100)
    names = {item["employee_id"]: item["name"] for item in employees}
    records = await get_db().attendance.find({"company_id": user["company_id"], "timestamp": {"$gte": start, "$lte": end}}).sort("timestamp", 1).to_list(500)
    rows = []
    grouped = {}
    for record in records:
        grouped.setdefault(record["employee_id"], []).append(record)
    for employee_id, items in grouped.items():
        rows.append({"employee_id": employee_id, "employee_name": names.get(employee_id, employee_id), "date": local_date_key(items[0]["timestamp"], timezone), "login": next((i["timestamp"] for i in items if i["type"] == "login"), None), "logout": next((i["timestamp"] for i in reversed(items) if i["type"] == "logout"), None), "status": "In Progress" if items[-1]["type"] == "login" else "Completed"})
    return {"success": True, "data": rows}


@router.get("/summary")
async def summary(user=Depends(current_user)):
    start, end = day_range_utc(tz=get_settings().company_timezone)
    employees = await get_db().employees.find({"company_id": user["company_id"]}).to_list(100)
    records = await get_db().attendance.find({"company_id": user["company_id"], "timestamp": {"$gte": start, "$lte": end}}).to_list(500)
    return {"success": True, "data": {"total_employees": len(employees), "registered_faces": len([e for e in employees if e.get("face_embeddings")]), "present_today": len(set(r["employee_id"] for r in records if r["type"] == "login")), "records_today": len(records)}}
