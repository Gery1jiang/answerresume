from sqlalchemy.orm import Session as DBSession
from services.models import ApplicantProfile
from datetime import datetime


class ApplicantProfileService:
    """Per-user profile"""

    def get(self, db: DBSession, user_id=None) -> ApplicantProfile:
        """Get or create profile for user"""
        profile = None
        if user_id and str(user_id).strip():
            profile = db.query(ApplicantProfile).filter(ApplicantProfile.user_id == user_id).first()
        if not profile:
            profile = ApplicantProfile(user_id=user_id or 0)
            db.add(profile)
            db.commit()
            db.refresh(profile)
        return profile

    def update(self, db: DBSession, data: dict, user_id=None) -> ApplicantProfile:
        """Update profile fields."""
        profile = self.get(db, user_id)
        allowed_fields = {"home_address", "home_lng", "home_lat", "default_travel_mode", "interview_duration_min", "min_gap_min", "max_daily_interviews", "workday_start", "workday_end"}
        for key, value in data.items():
            if key in allowed_fields and value is not None:
                setattr(profile, key, value)
        profile.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(profile)
        return profile


applicant_profile_service = ApplicantProfileService()
