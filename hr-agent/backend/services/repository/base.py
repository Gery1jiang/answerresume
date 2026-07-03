from __future__ import annotations
from typing import TypeVar, Generic, Any
from sqlalchemy.orm import Session

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """泛型 Repository：每个 ORM 模型对应一个子类，实现 get_model()。"""

    def __init__(self, db: Session):
        self.db = db

    def get_model(self) -> type[T]:
        raise NotImplementedError

    @property
    def model(self) -> type[T]:
        return self.get_model()

    # ── CRUD ──────────────────────────────────────────

    def get_by_id(self, id_val: str | int) -> T | None:
        return self.db.get(self.get_model(), id_val)

    _OPERATORS = {
        "__gte": "__ge__",
        "__lte": "__le__",
        "__gt": "__gt__",
        "__lt": "__lt__",
        "__ne": "__ne__",
        "__in": "__in__",
    }

    def _apply_filters(self, q, filters: dict):
        for k, v in filters.items():
            if v is None:
                continue
            op = "__eq__"
            col_name = k
            for suffix, mapped_op in self._OPERATORS.items():
                if k.endswith(suffix):
                    op = mapped_op
                    col_name = k[: -len(suffix)]
                    break
            col = getattr(self.get_model(), col_name, None)
            if col is None:
                continue
            if op == "__eq__":
                q = q.filter(col == v)
            elif op == "__ne__":
                q = q.filter(col != v)
            elif op == "__in__":
                q = q.filter(col.in_(v))
            elif op == "__ge__":
                q = q.filter(col >= v)
            elif op == "__le__":
                q = q.filter(col <= v)
            elif op == "__gt__":
                q = q.filter(col > v)
            elif op == "__lt__":
                q = q.filter(col < v)
        return q

    def list(self, **filters) -> list[T]:
        return self._apply_filters(self.db.query(self.get_model()), filters).all()

    def list_by_user(self, user_id: str, **filters) -> list[T]:
        q = self.db.query(self.get_model()).filter(
            self.get_model().user_id == user_id  # type: ignore
        )
        return self._apply_filters(q, filters).all()

    def create(self, **data) -> T:
        obj = self.get_model()(**data)
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def update(self, id_val: str | int, **data) -> T | None:
        obj = self.get_by_id(id_val)
        if not obj:
            return None
        for k, v in data.items():
            if v is not None and hasattr(obj, k):
                setattr(obj, k, v)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete(self, id_val: str | int) -> bool:
        obj = self.get_by_id(id_val)
        if not obj:
            return False
        self.db.delete(obj)
        self.db.commit()
        return True

    def count(self, **filters) -> int:
        return self._apply_filters(self.db.query(self.get_model()), filters).count()
