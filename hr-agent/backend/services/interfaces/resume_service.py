from abc import ABC, abstractmethod


class ResumeServiceInterface(ABC):
    """简历服务：生成、查询。"""

    @abstractmethod
    def save_resume(self, jd: str, target_job: str, user_id: str, raw_content: str = "") -> int:
        ...

    @abstractmethod
    def get_resume_by_id(self, resume_id: int) -> dict | None:
        ...

    @abstractmethod
    def list_by_user(self, user_id: str, limit: int = 50) -> list[dict]:
        ...

    @abstractmethod
    def count_by_user(self, user_id: str) -> int:
        ...
