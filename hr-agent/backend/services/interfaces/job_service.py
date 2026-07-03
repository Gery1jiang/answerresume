from abc import ABC, abstractmethod


class JobService(ABC):
    """岗位服务：爬取、匹配、搜索。"""

    @abstractmethod
    def crawl(self, keywords: str, city: str, platform: str, max_count: int, user_id: str) -> list[dict]:
        ...

    @abstractmethod
    def match(self, jd_text: str, user_id: str, salary_str: str = "", city_str: str = "", work_address: str = "") -> dict:
        ...

    @abstractmethod
    def search(self, user_id: str, keywords: str = "", city: str = "", limit: int = 20) -> list[dict]:
        ...
