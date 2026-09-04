import json
from pathlib import Path
from types import SimpleNamespace
from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ReturnDocument
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError
from .config import get_settings

client: AsyncIOMotorClient | None = None
db: AsyncIOMotorDatabase | None = None
using_local_json = False


def _clean(value):
    if isinstance(value, ObjectId):
        return str(value)
    if hasattr(value, "isoformat"):
        return {"$date": value.isoformat()}
    if isinstance(value, list):
        return [_clean(item) for item in value]
    if isinstance(value, dict):
        return {key: _clean(item) for key, item in value.items()}
    return value


def _restore(value):
    from datetime import datetime
    if isinstance(value, dict) and "$date" in value:
        return datetime.fromisoformat(value["$date"])
    if isinstance(value, list):
        return [_restore(item) for item in value]
    if isinstance(value, dict):
        return {key: _restore(item) for key, item in value.items()}
    return value


def _same(left, right) -> bool:
    if isinstance(left, ObjectId) or isinstance(right, ObjectId):
        return str(left) == str(right)
    return left == right


def _match(doc, query) -> bool:
    for key, expected in (query or {}).items():
        actual = doc.get(key)
        if isinstance(expected, dict):
            for op, value in expected.items():
                if op == "$exists" and ((key in doc) != value):
                    return False
                if op == "$ne" and _same(actual, value):
                    return False
                if op == "$gte" and not (actual >= value):
                    return False
                if op == "$lte" and not (actual <= value):
                    return False
        elif not _same(actual, expected):
            return False
    return True


class LocalCursor:
    def __init__(self, docs):
        self.docs = list(docs)

    def sort(self, key, direction=1):
        self.docs.sort(key=lambda item: item.get(key), reverse=direction < 0)
        return self

    def limit(self, count):
        self.docs = self.docs[:count]
        return self

    async def to_list(self, length):
        return self.docs[:length]

    def __aiter__(self):
        self.index = 0
        return self

    async def __anext__(self):
        if self.index >= len(self.docs):
            raise StopAsyncIteration
        item = self.docs[self.index]
        self.index += 1
        return item


class LocalCollection:
    def __init__(self, database, name):
        self.database = database
        self.name = name

    @property
    def docs(self):
        return self.database.data.setdefault(self.name, [])

    async def create_index(self, *args, **kwargs):
        return None

    def find(self, query=None):
        return LocalCursor([doc for doc in self.docs if _match(doc, query)])

    async def find_one(self, query=None):
        return next((doc for doc in self.docs if _match(doc, query)), None)

    async def insert_one(self, doc):
        doc = dict(doc)
        doc.setdefault("_id", ObjectId())
        self._ensure_unique(doc)
        self.docs.append(doc)
        self.database.save()
        return SimpleNamespace(inserted_id=doc["_id"])

    async def delete_one(self, query):
        for index, doc in enumerate(self.docs):
            if _match(doc, query):
                del self.docs[index]
                self.database.save()
                return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)

    async def update_one(self, query, update):
        doc = await self.find_one(query)
        if not doc:
            return SimpleNamespace(matched_count=0, modified_count=0)
        self._apply(doc, update)
        self.database.save()
        return SimpleNamespace(matched_count=1, modified_count=1)

    async def find_one_and_update(self, query, update, return_document=ReturnDocument.AFTER):
        doc = await self.find_one(query)
        if not doc:
            return None
        self._apply(doc, update)
        self.database.save()
        return doc

    async def count_documents(self, query):
        return len([doc for doc in self.docs if _match(doc, query)])

    def _apply(self, doc, update):
        for key, value in update.get("$set", {}).items():
            doc[key] = value
        for key, value in update.get("$push", {}).items():
            target = doc.setdefault(key, [])
            if isinstance(value, dict) and "$each" in value:
                target.extend(value["$each"])
                if "$slice" in value:
                    keep = int(value["$slice"])
                    doc[key] = target[keep:] if keep < 0 else target[:keep]
            else:
                target.append(value)

    def _ensure_unique(self, doc):
        checks = {
            "companies": ("admin_email",),
            "users": ("email",),
            "employees": ("company_id", "employee_id"),
        }
        fields = checks.get(self.name)
        if not fields:
            return
        for existing in self.docs:
            if all(_same(existing.get(field), doc.get(field)) for field in fields):
                raise DuplicateKeyError(f"Duplicate local key for {self.name}: {', '.join(fields)}")


class LocalDatabase:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data = _restore(json.loads(self.path.read_text(encoding="utf-8"))) if self.path.exists() else {}

    def __getattr__(self, name):
        return LocalCollection(self, name)

    async def command(self, command):
        return {"ok": 1, "storage": "local-json"}

    def save(self):
        self.path.write_text(json.dumps(_clean(self.data), indent=2), encoding="utf-8")


async def connect_db() -> None:
    global client, db, using_local_json
    if db is not None:
        return
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongodb_uri, serverSelectionTimeoutMS=2000)
    db = client.get_database(settings.mongodb_database)
    try:
        await db.command("ping")
        await db.companies.create_index("admin_email", unique=True)
        await db.users.create_index("email", unique=True)
        await db.employees.create_index([("company_id", 1), ("employee_id", 1)], unique=True)
        await db.attendance.create_index([("company_id", 1), ("employee_id", 1), ("timestamp", 1)])
        await db.password_otps.create_index("expires_at", expireAfterSeconds=0)
    except ServerSelectionTimeoutError as error:
        print(f"[AttendXsuite] MongoDB not reachable, using local JSON DB: {error}")
        db = LocalDatabase(Path(__file__).resolve().parents[1] / "local-data" / "attendxsuite.json")
        using_local_json = True


def get_db():
    if db is None:
        raise RuntimeError("Database is not connected")
    return db


async def check_db() -> dict:
    try:
        await get_db().command({"ping": 1})
        if using_local_json:
            return {"ok": True, "message": "Using local JSON DB because MongoDB is not reachable."}
        return {"ok": True, "message": "MongoDB connection is healthy."}
    except (RuntimeError, PyMongoError) as error:
        return {"ok": False, "message": f"Database is not reachable: {error}"}
