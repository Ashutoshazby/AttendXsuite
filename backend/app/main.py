from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import get_settings
from .database import check_db, connect_db
from .routers import auth, employees, faces, attendance

settings = get_settings()
app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|10\..*|172\.(1[6-9]|2\d|3[0-1])\..*|192\.168\..*|[a-z0-9-]+\.loca\.lt)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await connect_db()


@app.get("/health")
async def health():
    return {"success": True, "message": "AttendXsuite backend running", "data": {"database": await check_db()}}


app.include_router(auth.router)
app.include_router(employees.router)
app.include_router(faces.router)
app.include_router(attendance.router)
