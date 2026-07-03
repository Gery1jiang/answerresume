import httpx
from sqlalchemy.orm import Session as DBSession
from sqlalchemy import desc, nullslast
from services.models import InterviewGuide, ReportGenerationTask
from datetime import datetime
from typing import Optional
from services.usage_service import usage_service


class InterviewGuideService:

    def list(
        self,
        db: DBSession,
        page: int = 1,
        size: int = 20,
        company: str = "",
        status: str = "",
        user_id=None,
    ) -> dict:
        query = db.query(InterviewGuide)
        if user_id:
            query = query.filter(InterviewGuide.user_id == user_id)
        if company:
            query = query.filter(InterviewGuide.company_name.ilike(f"%{company}%"))
        if status:
            query = query.filter(InterviewGuide.status == status)

        total = query.count()
        items = query.order_by(nullslast(desc(InterviewGuide.interview_time))).offset((page - 1) * size).limit(size).all()

        return {
            "total": total,
            "page": page,
            "size": size,
            "items": [self._to_dict(item) for item in items],
        }

    def get(self, db: DBSession, guide_id: int, user_id=None) -> Optional[dict]:
        q = db.query(InterviewGuide).filter(InterviewGuide.id == guide_id)
        if user_id:
            q = q.filter(InterviewGuide.user_id == user_id)
        item = q.first()
        return self._to_dict(item) if item else None

    @staticmethod
    def _parse_iso(dt_str: str) -> datetime:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))

    def _calc_commute(self, item: InterviewGuide, user_id=None):
        if not item.interview_address_lng or not item.interview_address_lat:
            return
        try:
            from services.applicant_profile_service import applicant_profile_service
            from services.database import SessionLocal
            db2 = SessionLocal()
            try:
                profile = applicant_profile_service.get(db2, user_id)
                if not profile or not profile.get("home_lng") or not profile.get("home_lat"):
                    return
                import httpx
                mode = profile.get("default_travel_mode", "transit")
                origin = f"{profile['home_lng']},{profile['home_lat']}"
                dest = f"{item.interview_address_lng},{item.interview_address_lat}"
                from config import settings as app_settings
                amap_key = getattr(app_settings, "AMAP_API_KEY", "")
                if not amap_key:
                    return
                resp = httpx.get(
                    "https://restapi.amap.com/v3/direction/transit/integrated" if mode == "transit" else f"https://restapi.amap.com/v3/direction/{mode}",
                    params={
                        "key": amap_key,
                        "origin": origin,
                        "destination": dest,
                        "city": "",
                        "cityd": "",
                    },
                    timeout=10,
                )
                data = resp.json()
                if data.get("status") == "1" and data.get("route"):
                    if mode == "transit":
                        plans = data["route"].get("transits", [])
                        if plans:
                            item.commute_duration_min = plans[0].get("duration", 0) // 60
                            item.commute_distance_km = plans[0].get("distance", 0) / 1000
                    else:
                        paths = data["route"].get("paths", [])
                        if paths:
                            item.commute_duration_min = paths[0].get("duration", 0) // 60
                            item.commute_distance_km = paths[0].get("distance", 0) / 1000
                    if user_id:
                        usage_service.record(user_id=user_id, event_type="search_api", model="amap", search_calls=1)
            finally:
                db2.close()
        except Exception:
            pass

    def create(self, db: DBSession, data: dict, user_id=None) -> dict:
        item = InterviewGuide(
            company_name=data["company_name"],
            company_description=data.get("company_description", ""),
            job_title=data["job_title"],
            hr_name=data.get("hr_name", ""),
            hr_phone=data.get("hr_phone", ""),
            hr_email=data.get("hr_email", ""),
            interview_address=data.get("interview_address", ""),
            interview_address_lng=data.get("interview_address_lng"),
            interview_address_lat=data.get("interview_address_lat"),
            address_type=data.get("address_type", "offline"),
            video_link=data.get("video_link", ""),
            salary=data.get("salary", ""),
            interview_round=data.get("interview_round", ""),
            interview_time=self._parse_iso(data["interview_time"]) if isinstance(data.get("interview_time"), str) else data.get("interview_time"),
            status="pending",
            result=data.get("result", ""),
            source=data.get("source", "manual"),
            jd_text=data.get("jd_text", ""),
            jd_parsed=data.get("jd_parsed", "{}"),
            user_id=user_id,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        self._calc_commute(item, user_id)
        db.commit()
        db.refresh(item)
        return self._to_dict(item)

    def update(self, db: DBSession, guide_id: int, data: dict, user_id=None) -> Optional[dict]:
        q = db.query(InterviewGuide).filter(InterviewGuide.id == guide_id)
        if user_id:
            q = q.filter(InterviewGuide.user_id == user_id)
        item = q.first()
        if not item:
            return None

        allowed_fields = {
            "company_name", "company_description", "job_title", "hr_name", "hr_phone", "hr_email",
            "interview_address", "interview_address_lng", "interview_address_lat",
            "address_type", "video_link", "interview_round", "salary", "result",
            "interview_time", "status", "commute_duration_min", "commute_distance_km",
            "conflict_warnings", "guide_content", "jd_text", "jd_parsed",
        }
        for key, value in data.items():
            if key in allowed_fields and value is not None:
                if key == "interview_time" and isinstance(value, str):
                    value = self._parse_iso(value)
                setattr(item, key, value)

        item.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(item)
        self._calc_commute(item, user_id)
        db.commit()
        db.refresh(item)
        return self._to_dict(item)

    def delete(self, db: DBSession, guide_id: int, user_id=None) -> bool:
        q = db.query(InterviewGuide).filter(InterviewGuide.id == guide_id)
        if user_id:
            q = q.filter(InterviewGuide.user_id == user_id)
        item = q.first()
        if not item:
            return False
        db.query(ReportGenerationTask).filter(ReportGenerationTask.guide_id == guide_id).delete()
        db.delete(item)
        db.commit()
        return True

    def _to_dict(self, item: InterviewGuide) -> dict:
        import json
        return {
            "id": item.id,
            "company_name": item.company_name,
            "company_description": item.company_description,
            "job_title": item.job_title,
            "hr_name": item.hr_name,
            "hr_phone": item.hr_phone,
            "hr_email": item.hr_email,
            "interview_address": item.interview_address,
            "interview_address_lng": item.interview_address_lng,
            "interview_address_lat": item.interview_address_lat,
            "address_type": item.address_type,
            "video_link": item.video_link,
            "salary": item.salary,
            "interview_round": item.interview_round,
            "interview_time": item.interview_time.isoformat() if item.interview_time else None,
            "status": item.status,
            "result": item.result,
            "commute_duration_min": item.commute_duration_min,
            "commute_distance_km": item.commute_distance_km,
            "conflict_warnings": json.loads(item.conflict_warnings) if item.conflict_warnings else [],
            "guide_content": json.loads(item.guide_content) if item.guide_content else {},
            "generated_report_id": item.generated_report_id,
            "source": item.source,
            "session_id": item.session_id,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
            "jd_text": item.jd_text,
            "jd_parsed": json.loads(item.jd_parsed) if item.jd_parsed else {},
            "generated_report_md": item.generated_report_md,
        }


interview_guide_service = InterviewGuideService()
