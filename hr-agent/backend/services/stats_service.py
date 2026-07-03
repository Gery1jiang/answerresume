from sqlalchemy.orm import Session as DBSession
from .models import Stats
from .enums import EventType

def record_event(event_type: EventType, session_id: str, db: DBSession, user_id: str = ""):
    stat = Stats(event_type=event_type.value, session_id=session_id, user_id=user_id or "")
    db.add(stat)
    db.commit()
