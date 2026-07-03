from __future__ import annotations
import asyncio
import inspect
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    FILE_UPLOADED = "file.uploaded"
    JOB_CRAWLED = "job.crawled"
    JOB_MATCHED = "job.matched"
    RESUME_GENERATED = "resume.generated"
    INTERVIEW_CREATED = "interview.created"
    CONVERSATION_SAVED = "conversation.saved"


@dataclass
class Event:
    type: EventType
    data: dict = field(default_factory=dict)
    user_id: str = ""


Handler = Callable[[Event], Any]


class EventBus:
    def __init__(self):
        self._handlers: dict[EventType, list[Handler]] = {}

    def on(self, event_type: EventType):
        def decorator(fn: Handler) -> Handler:
            self._handlers.setdefault(event_type, []).append(fn)
            return fn
        return decorator

    def register(self, event_type: EventType, fn: Handler):
        self._handlers.setdefault(event_type, []).append(fn)

    def emit(self, event_type: EventType, data: dict | None = None, user_id: str = ""):
        event = Event(type=event_type, data=data or {}, user_id=user_id)
        for handler in self._handlers.get(event_type, []):
            try:
                if inspect.iscoroutinefunction(handler):
                    asyncio.create_task(handler(event))
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"EventBus handler failed for {event_type}: {e}", exc_info=True)

    def emit_sync(self, event_type: EventType, data: dict | None = None, user_id: str = ""):
        """Synchronous emit — handlers run in current thread/event loop."""
        event = Event(type=event_type, data=data or {}, user_id=user_id)
        for handler in self._handlers.get(event_type, []):
            try:
                if inspect.iscoroutinefunction(handler):
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(handler(event))
                    else:
                        loop.run_until_complete(handler(event))
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"EventBus sync handler failed for {event_type}: {e}", exc_info=True)

    def clear(self):
        self._handlers.clear()


event_bus = EventBus()
