"""依赖注入容器。

Repository 和 Service 都在此组装。每个请求创建一个 Container 实例，
确保共享同一个 DB session。

使用方式：
    from services.container import Container

    container = Container(user_id)
    file_result = container.file_service.parse_document(path)
    container.close()
"""

from sqlalchemy.orm import Session
from services.database import SessionLocal
from services.repository.container import RepoContainer
from services.impl.file_service import FileServiceImpl


class Container:
    """应用容器：组装 Repository + Service。"""

    def __init__(self, user_id: str = "", db: Session | None = None):
        self._user_id = user_id
        self._rc = RepoContainer(db)
        self._services = {}

    @classmethod
    def from_env(cls, user_id: str = "") -> "Container":
        return cls(user_id=user_id)

    def close(self):
        self._rc.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # ── repositories ────────────────────────────────────
    @property
    def repos(self) -> RepoContainer:
        return self._rc

    # ── services ─────────────────────────────────────────

    @property
    def file_service(self) -> FileServiceImpl:
        if "file" not in self._services:
            self._services["file"] = FileServiceImpl()
        return self._services["file"]
