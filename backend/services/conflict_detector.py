from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session as DBSession
from services.models import InterviewGuide, ApplicantProfile
from services.amap_client import AmapClient
from services.applicant_profile_service import applicant_profile_service


class ConflictDetector:
    async def check(
        self,
        db: DBSession,
        interview_time: datetime,
        interview_lng: Optional[float],
        interview_lat: Optional[float],
        interview_address: str = "",
        exclude_guide_id: Optional[int] = None,
    ) -> list[dict]:
        warnings: list[dict] = []

        profile = applicant_profile_service.get(db)
        duration_min = profile.interview_duration_min or 60
        min_gap = profile.min_gap_min or 120
        max_daily = profile.max_daily_interviews or 3

        interview_end = interview_time + timedelta(minutes=duration_min)
        interview_date = interview_time.date()

        day_start = datetime(interview_date.year, interview_date.month, interview_date.day)
        day_end = day_start + timedelta(days=1)

        existing = db.query(InterviewGuide).filter(
            InterviewGuide.interview_time >= day_start,
            InterviewGuide.interview_time < day_end,
            InterviewGuide.status.in_(["pending", "confirmed"]),
        )
        if exclude_guide_id:
            existing = existing.filter(InterviewGuide.id != exclude_guide_id)
        existing = existing.all()

        if len(existing) >= max_daily:
            warnings.append({
                "type": "max_daily_count",
                "severity": "warning",
                "message": f"当天已有{len(existing)}场面试，已达到最大日面试次数（{max_daily}场）",
            })

        amap = AmapClient()

        for ex in existing:
            ex_start = ex.interview_time
            ex_end = ex_start + timedelta(minutes=duration_min)

            if interview_time < ex_end and interview_end > ex_start:
                overlap_min = (min(interview_end, ex_end) - max(interview_time, ex_start)).seconds // 60
                warnings.append({
                    "type": "time_overlap",
                    "severity": "error",
                    "message": f"与「{ex.company_name}」的面试时间冲突（重叠{overlap_min}分钟）",
                })

            both_have_coords = (
                interview_lng is not None
                and interview_lat is not None
                and ex.interview_address_lng is not None
                and ex.interview_address_lat is not None
            )
            if both_have_coords:
                if interview_end < ex_start:
                    gap_min = (ex_start - interview_end).seconds // 60
                    route = await amap.driving_route(
                        interview_lng, interview_lat,
                        ex.interview_address_lng, ex.interview_address_lat,
                    )
                    commute_min = route["duration_minutes"] if route else 0
                    if commute_min > gap_min:
                        warnings.append({
                            "type": "commute_gap",
                            "severity": "warning",
                            "message": f"从该面试到「{ex.company_name}」需{commute_min}分钟车程，但两场之间仅间隔{gap_min}分钟",
                        })

                if ex_end < interview_time:
                    gap_min = (interview_time - ex_end).seconds // 60
                    route = await amap.driving_route(
                        ex.interview_address_lng, ex.interview_address_lat,
                        interview_lng, interview_lat,
                    )
                    commute_min = route["duration_minutes"] if route else 0
                    if commute_min > gap_min:
                        warnings.append({
                            "type": "commute_gap",
                            "severity": "warning",
                            "message": f"从「{ex.company_name}」到该面试需{commute_min}分钟车程，但两场之间仅间隔{gap_min}分钟",
                        })

        if interview_lng and interview_lat and profile.home_lng and profile.home_lat:
            mode = profile.default_travel_mode or "driving"
            route = None
            if mode == "driving":
                route = await amap.driving_route(profile.home_lng, profile.home_lat, interview_lng, interview_lat)
            elif mode == "transit":
                route = await amap.transit_route(profile.home_lng, profile.home_lat, interview_lng, interview_lat)
            elif mode == "walking":
                route = await amap.walking_route(profile.home_lng, profile.home_lat, interview_lng, interview_lat)

            if route and route["duration_minutes"] > 90:
                warnings.append({
                    "type": "long_commute",
                    "severity": "info",
                    "message": f"从家到面试地点需{route['duration_minutes']}分钟（{mode}），通勤时间较长",
                })

        await amap.close()
        return warnings


conflict_detector = ConflictDetector()
