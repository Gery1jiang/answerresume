"""Tests for BaseRepository."""

from datetime import datetime
from services.repository.base import BaseRepository
from services.models.conversation import Conversation
from services.models.session import Session


class TestBaseRepository:
    def test_create_and_get_by_id(self, db_session):
        repo = type("TestRepo", (BaseRepository,), {"get_model": lambda s: Session})(db_session)
        obj = repo.create(id="sess-1", user_id="user-1", is_active=True)
        assert obj.id == "sess-1"
        assert obj.user_id == "user-1"

        fetched = repo.get_by_id("sess-1")
        assert fetched is not None
        assert fetched.id == "sess-1"

    def test_get_by_id_returns_none(self, db_session):
        repo = type("TestRepo", (BaseRepository,), {"get_model": lambda s: Session})(db_session)
        assert repo.get_by_id("nonexistent") is None

    def test_list_with_filters(self, db_session):
        repo = type("TestRepo", (BaseRepository,), {"get_model": lambda s: Session})(db_session)
        repo.create(id="s1", user_id="u1", is_active=True)
        repo.create(id="s2", user_id="u1", is_active=False)
        repo.create(id="s3", user_id="u2", is_active=True)

        results = repo.list(user_id="u1")
        assert len(results) == 2

        results = repo.list(user_id="u1", is_active=True)
        assert len(results) == 1
        assert results[0].id == "s1"

    def test_list_by_user(self, db_session):
        repo = type("TestRepo", (BaseRepository,), {"get_model": lambda s: Session})(db_session)
        repo.create(id="s1", user_id="u1")
        repo.create(id="s2", user_id="u2")
        repo.create(id="s3", user_id="u1")

        results = repo.list_by_user("u1")
        assert len(results) == 2
        assert {r.id for r in results} == {"s1", "s3"}

    def test_update(self, db_session):
        repo = type("TestRepo", (BaseRepository,), {"get_model": lambda s: Session})(db_session)
        repo.create(id="s1", user_id="u1", is_active=True)
        updated = repo.update("s1", is_active=False)
        assert updated is not None
        assert updated.is_active is False

    def test_update_nonexistent(self, db_session):
        repo = type("TestRepo", (BaseRepository,), {"get_model": lambda s: Session})(db_session)
        assert repo.update("no-such-id", is_active=False) is None

    def test_delete(self, db_session):
        repo = type("TestRepo", (BaseRepository,), {"get_model": lambda s: Session})(db_session)
        repo.create(id="s1", user_id="u1")
        assert repo.delete("s1") is True
        assert repo.get_by_id("s1") is None

    def test_delete_nonexistent(self, db_session):
        repo = type("TestRepo", (BaseRepository,), {"get_model": lambda s: Session})(db_session)
        assert repo.delete("no-such-id") is False

    def test_count(self, db_session):
        repo = type("TestRepo", (BaseRepository,), {"get_model": lambda s: Session})(db_session)
        repo.create(id="s1", user_id="u1", is_active=True)
        repo.create(id="s2", user_id="u1", is_active=False)
        assert repo.count(user_id="u1") == 2
        assert repo.count(user_id="u1", is_active=True) == 1

    def test_apply_filters_gte_lte(self, db_session):
        """Test comparison operators on a model with numeric fields."""
        repo = type("TestRepo", (BaseRepository,), {"get_model": lambda s: Session})(db_session)
        from datetime import datetime
        now = datetime.utcnow()
        repo.create(id="s1", user_id="u1", created_at=now)
        older = datetime(2020, 1, 1)
        repo.create(id="s2", user_id="u1", created_at=older)

        results = repo.list(created_at__gte=datetime(2023, 1, 1))
        assert len(results) == 1
        assert results[0].id == "s1"

        results = repo.list(created_at__lt=datetime(2023, 1, 1))
        assert len(results) == 1
        assert results[0].id == "s2"
