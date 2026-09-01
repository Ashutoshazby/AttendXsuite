from datetime import timedelta
from secrets import randbelow
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from ..database import get_db
from ..dependencies import current_user, require_role
from ..services.security import create_token, hash_password, verify_password
from ..utils.timezone import now_utc

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterCompany(BaseModel):
    company_name: str
    name: str
    email: EmailStr
    password: str


class LoginPayload(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordPayload(BaseModel):
    email: EmailStr


class ResetPasswordPayload(BaseModel):
    email: EmailStr
    otp: str
    new_password: str


def public_user(user: dict, company: dict | None = None) -> dict:
    return {
        "id": str(user["_id"]),
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
        "company_id": user["company_id"],
        "company_name": company.get("name", "") if company else ""
    }


@router.post("/register-company")
async def register_company(payload: RegisterCompany):
    if len(payload.password) < 6:
        raise HTTPException(status_code=422, detail="Password must be at least 6 characters")
    db = get_db()
    email = payload.email.lower()
    company = {"name": payload.company_name, "admin_email": email, "timezone": "Asia/Kolkata", "created_at": now_utc()}
    company_result = await db.companies.insert_one(company)
    user = {
        "company_id": str(company_result.inserted_id),
        "name": payload.name,
        "email": email,
        "password_hash": hash_password(payload.password),
        "role": "admin",
        "active": True,
        "created_at": now_utc()
    }
    try:
        user_result = await db.users.insert_one(user)
    except Exception:
        await db.companies.delete_one({"_id": company_result.inserted_id})
        raise HTTPException(status_code=409, detail="Email already exists")
    user["_id"] = user_result.inserted_id
    token = create_token({"user_id": str(user_result.inserted_id), "company_id": user["company_id"], "role": "admin"})
    return {"success": True, "data": {"token": token, "user": public_user(user, {"name": payload.company_name})}}


@router.post("/login")
async def login(payload: LoginPayload):
    db = get_db()
    user = await db.users.find_one({"email": payload.email.lower(), "active": True})
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    company = await db.companies.find_one({"_id": ObjectId(user["company_id"])})
    token = create_token({"user_id": str(user["_id"]), "company_id": user["company_id"], "role": user["role"]})
    return {"success": True, "data": {"token": token, "user": public_user(user, company)}}


@router.get("/me")
async def me(user=Depends(current_user)):
    company = await get_db().companies.find_one({"_id": ObjectId(user["company_id"])})
    return {"success": True, "data": public_user(user, company)}


@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordPayload):
    db = get_db()
    user = await db.users.find_one({"email": payload.email.lower(), "active": True})
    if user:
        otp = f"{randbelow(900000) + 100000}"
        await db.password_otps.insert_one({
            "email": payload.email.lower(),
            "otp": otp,
            "expires_at": now_utc() + timedelta(minutes=10),
            "used": False
        })
        print(f"[AttendXsuite OTP] {payload.email.lower()} -> {otp}")
    return {"success": True, "message": "If the account exists, an OTP was generated in backend logs."}


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordPayload):
    if len(payload.new_password) < 6:
        raise HTTPException(status_code=422, detail="Password must be at least 6 characters")
    db = get_db()
    otp = await db.password_otps.find_one({"email": payload.email.lower(), "otp": payload.otp, "used": False, "expires_at": {"$gte": now_utc()}})
    if not otp:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")
    await db.users.update_one({"email": payload.email.lower()}, {"$set": {"password_hash": hash_password(payload.new_password)}})
    await db.password_otps.update_one({"_id": otp["_id"]}, {"$set": {"used": True}})
    return {"success": True, "message": "Password updated"}


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str = "user"


class UserPasswordUpdate(BaseModel):
    password: str


@router.post("/users")
async def create_user(payload: UserCreate, user=Depends(require_role("admin"))):
    if payload.role not in {"admin", "user"}:
        raise HTTPException(status_code=422, detail="Role must be admin or user")
    doc = {
        "company_id": user["company_id"],
        "name": payload.name,
        "email": payload.email.lower(),
        "password_hash": hash_password(payload.password),
        "role": payload.role,
        "active": True,
        "created_at": now_utc()
    }
    result = await get_db().users.insert_one(doc)
    doc["_id"] = result.inserted_id
    return {"success": True, "data": public_user(doc)}


@router.get("/users")
async def list_users(user=Depends(require_role("admin"))):
    users = await get_db().users.find({"company_id": user["company_id"], "active": True}).sort("created_at", -1).to_list(100)
    return {"success": True, "data": [public_user(item) for item in users]}


@router.put("/users/{user_id}/password")
async def update_user_password(user_id: str, payload: UserPasswordUpdate, user=Depends(require_role("admin"))):
    if len(payload.password) < 6:
        raise HTTPException(status_code=422, detail="Password must be at least 6 characters")
    result = await get_db().users.update_one(
        {"_id": ObjectId(user_id), "company_id": user["company_id"], "active": True},
        {"$set": {"password_hash": hash_password(payload.password), "updated_at": now_utc()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"success": True, "message": "Password updated"}


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, user=Depends(require_role("admin"))):
    if str(user["_id"]) == user_id:
        raise HTTPException(status_code=409, detail="You cannot delete your own admin account")
    target = await get_db().users.find_one({"_id": ObjectId(user_id), "company_id": user["company_id"], "active": True})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    active_admins = await get_db().users.count_documents({"company_id": user["company_id"], "role": "admin", "active": True})
    if target["role"] == "admin" and active_admins <= 1:
        raise HTTPException(status_code=409, detail="At least one admin must remain")
    await get_db().users.update_one({"_id": target["_id"]}, {"$set": {"active": False, "deleted_at": now_utc()}})
    return {"success": True, "message": "User deleted"}
