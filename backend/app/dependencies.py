from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from bson import ObjectId
from .database import get_db
from .services.security import decode_token

bearer = HTTPBearer(auto_error=False)


async def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        payload = decode_token(credentials.credentials)
        user = await get_db().users.find_one({"_id": ObjectId(payload["user_id"])})
        if not user:
            raise ValueError("missing user")
        user["_id"] = str(user["_id"])
        return user
    except Exception:
        raise HTTPException(status_code=401, detail="Authentication required")


def require_role(*roles: str):
    async def guard(user=Depends(current_user)):
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="You do not have permission for this action")
        return user
    return guard


def request_base_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")
