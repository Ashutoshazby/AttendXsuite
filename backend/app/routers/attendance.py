import asyncio
from collections import Counter
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from ..config import get_settings
from ..database import get_db
from ..dependencies import require_role
from ..services.face_engine import best_match, create_embeddings
from ..services.realtime import publish, subscribe, sse
from ..utils.timezone import day_range_utc, local_date_key, local_time_label, now_utc

router = APIRouter(prefix="/attendance", tags=["attendance"])
PUNCH_GAP_SECONDS = 60


class ScanPayload(BaseModel):
    frames: list[str]
    face_descriptors: list[list[float]] | None = None
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
    scores = []
    errors = []
    descriptors = [item for item in (payload.face_descriptors or []) if len(item) == 128]
    faces = [{"embedding": descriptor, "model": "face-api"} for descriptor in descriptors[: settings.face_scan_frame_count]] if descriptors else await create_embeddings(frames)
    for face in faces:
        try:
            match = best_match(face["embedding"], employees)
            votes.append(match["employee"]["employee_id"])
            scores.append({"employee_id": match["employee"]["employee_id"], "score": match["score"]})
        except HTTPException as error:
            errors.append(str(error.detail))
    if not votes:
        raise HTTPException(status_code=422, detail=errors[-1] if errors else "Face match is uncertain. Please scan again.")
    winner, count = Counter(votes).most_common(1)[0]
    second_count = Counter(votes).most_common(2)[1][1] if len(Counter(votes)) > 1 else 0
    winner_scores = [item["score"] for item in scores if item["employee_id"] == winner]
    average_score = sum(winner_scores) / len(winner_scores)
    if count == second_count:
        raise HTTPException(status_code=422, detail="Face match is uncertain. Please scan again.")
    if count < settings.face_scan_consensus and (count < 2 or average_score < settings.face_match_threshold + 0.08):
        raise HTTPException(status_code=422, detail="Face match is uncertain. Please scan again.")
    employee = await get_db().employees.find_one({"company_id": user["company_id"], "employee_id": winner})
    action = await attendance_type(user["company_id"], winner, now_utc())
    sample = (employee.get("face_samples") or [])[-1] if employee else {}
    return {"success": True, "data": {"employee_id": winner, "employee_name": employee["name"], "action": action, "confidence": round(average_score * 100), "face_preview": sample.get("image_base64", "")}}


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
async def today(user=Depends(require_role("admin"))):
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
        login_at = next((i["timestamp"] for i in items if i["type"] == "login"), None)
        logout_at = next((i["timestamp"] for i in reversed(items) if i["type"] == "logout"), None)
        rows.append({
            "employee_id": employee_id,
            "employee_name": names.get(employee_id, employee_id),
            "date": local_date_key(items[0]["timestamp"], timezone),
            "login": login_at,
            "logout": logout_at,
            "login_time": local_time_label(login_at, timezone),
            "logout_time": local_time_label(logout_at, timezone),
            "timezone": timezone,
            "status": "In Progress" if items[-1]["type"] == "login" else "Completed"
        })
    return {"success": True, "data": rows}


@router.get("/summary")
async def summary(user=Depends(require_role("admin"))):
    start, end = day_range_utc(tz=get_settings().company_timezone)
    employees = await get_db().employees.find({"company_id": user["company_id"]}).to_list(100)
    records = await get_db().attendance.find({"company_id": user["company_id"], "timestamp": {"$gte": start, "$lte": end}}).to_list(500)
    return {"success": True, "data": {"total_employees": len(employees), "registered_faces": len([e for e in employees if e.get("face_embeddings")]), "present_today": len(set(r["employee_id"] for r in records if r["type"] == "login")), "records_today": len(records)}}


@router.get("/payroll")
async def payroll(month: str | None = None, user=Depends(require_role("admin"))):
    settings = get_settings()
    tz = ZoneInfo(settings.company_timezone)
    today_local = now_utc().astimezone(tz)
    try:
        month_start_date = datetime.strptime(month or today_local.strftime("%Y-%m"), "%Y-%m").date().replace(day=1)
    except ValueError:
        raise HTTPException(status_code=422, detail="Month must use YYYY-MM format")
    if month_start_date.month == 12:
        next_month_date = month_start_date.replace(year=month_start_date.year + 1, month=1)
    else:
        next_month_date = month_start_date.replace(month=month_start_date.month + 1)
    start = datetime.combine(month_start_date, time.min, tzinfo=tz).astimezone(timezone.utc)
    end = datetime.combine(next_month_date, time.min, tzinfo=tz).astimezone(timezone.utc)
    employees = await get_db().employees.find({"company_id": user["company_id"]}).sort("name", 1).to_list(300)
    records = await get_db().attendance.find({"company_id": user["company_id"], "timestamp": {"$gte": start, "$lt": end}}).sort("timestamp", 1).to_list(2000)
    records_by_employee = {}
    for record in records:
        records_by_employee.setdefault(record["employee_id"], []).append(record)
    rows = []
    for employee in employees:
        items = records_by_employee.get(employee["employee_id"], [])
        open_login = None
        worked_seconds = 0
        worked_days = set()
        for item in items:
            if item["type"] == "login":
                open_login = item["timestamp"]
                worked_days.add(local_date_key(item["timestamp"], settings.company_timezone))
            elif item["type"] == "logout" and open_login:
                worked_seconds += max(0, (item["timestamp"] - open_login).total_seconds())
                open_login = None
        worked_hours = round(worked_seconds / 3600, 2)
        standard_daily_hours = float(employee.get("standard_daily_hours") or 8)
        expected_hours = round(len(worked_days) * standard_daily_hours, 2)
        overtime_hours = round(max(0, worked_hours - expected_hours), 2)
        monthly_salary = float(employee.get("monthly_salary") or employee.get("salary") or 0)
        overtime_rate = float(employee.get("overtime_hourly_rate") or 0)
        overtime_pay = round(overtime_hours * overtime_rate, 2)
        rows.append({
            "employee_id": employee["employee_id"],
            "employee_name": employee["name"],
            "department": employee.get("department", "General"),
            "month": month_start_date.strftime("%Y-%m"),
            "worked_days": len(worked_days),
            "working_days_per_week": employee.get("working_days_per_week", 6),
            "worked_hours": worked_hours,
            "expected_hours": expected_hours,
            "overtime_hours": overtime_hours,
            "monthly_salary": monthly_salary,
            "overtime_pay": overtime_pay,
            "total_pay": round(monthly_salary + overtime_pay, 2)
        })
    return {"success": True, "data": rows}
