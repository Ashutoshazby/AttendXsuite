import asyncio
import json
from collections import defaultdict

queues: dict[str, set[asyncio.Queue]] = defaultdict(set)


async def subscribe(company_id: str):
    queue: asyncio.Queue = asyncio.Queue()
    queues[company_id].add(queue)
    try:
        yield queue
    finally:
        queues[company_id].discard(queue)


async def publish(company_id: str, event: str, data: dict):
    for queue in list(queues.get(company_id, set())):
        await queue.put({"event": event, "data": data})


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"
