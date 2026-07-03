from services.models.applicant_profile import ApplicantProfile
from .base import BaseRepository


class ApplicantProfileRepository(BaseRepository[ApplicantProfile]):
    def get_model(self) -> type[ApplicantProfile]:
        return ApplicantProfile

    def get_by_user(self, user_id: str) -> ApplicantProfile | None:
        return self.db.query(ApplicantProfile).filter(
            ApplicantProfile.user_id == user_id
        ).first()

    def upsert(self, user_id: str, **data) -> ApplicantProfile:
        profile = self.get_by_user(user_id)
        if profile:
            for k, v in data.items():
                if v is not None and hasattr(profile, k):
                    setattr(profile, k, v)
            self.db.commit()
            self.db.refresh(profile)
            return profile
        return self.create(user_id=user_id, **data)
