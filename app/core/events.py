import asyncio
import json
import logging
from typing import AsyncGenerator, Dict, Any

logger = logging.getLogger(__name__)


class EventBroadcaster:
    """Dispatches real-time pipeline telemetry and SSE events to subscribed dashboard clients."""

    def __init__(self):
        self._subscribers = set()
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue:
        queue = asyncio.Queue()
        async with self._lock:
            self._subscribers.add(queue)
        logger.info(f"New SSE client connected (total: {len(self._subscribers)})")
        return queue

    async def unsubscribe(self, queue: asyncio.Queue) -> None:
        async with self._lock:
            if queue in self._subscribers:
                self._subscribers.remove(queue)
        logger.info(f"SSE client disconnected (remaining: {len(self._subscribers)})")

    async def broadcast(self, event_type: str, data: Dict[str, Any]) -> None:
        """Broadcasts event payload to all active SSE queues."""
        message = {
            "event": event_type,
            "data": data
        }
        async with self._lock:
            for queue in list(self._subscribers):
                try:
                    queue.put_nowait(message)
                except Exception as e:
                    logger.warning(f"Failed to queue event for subscriber: {e}")

    async def event_generator(self) -> AsyncGenerator[str, None]:
        """Yields Server-Sent Events formatted as SSE standard data blocks."""
        queue = await self.subscribe()
        try:
            while True:
                msg = await queue.get()
                event_name = msg.get("event", "message")
                data_json = json.dumps(msg.get("data", {}))
                yield f"event: {event_name}\ndata: {data_json}\n\n"
        finally:
            await self.unsubscribe(queue)


broadcaster = EventBroadcaster()

