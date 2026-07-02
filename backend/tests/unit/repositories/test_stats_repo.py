"""Tests for StatsRepository."""

from datetime import datetime
from services.repository.container import RepoContainer


class TestStatsRepository:
    def test_record_and_count_events(self, repo_container: RepoContainer):
        repo = repo_container.stats
        repo.record_event("u1", "VISIT")
        repo.record_event("u1", "VISIT")
        repo.record_event("u1", "CHAT")

        assert repo.count_events("u1", "VISIT") == 2
        assert repo.count_events("u1", "CHAT") == 1
        assert repo.count_events("u1", "DOWNLOAD") == 0

    def test_count_events_with_since(self, repo_container: RepoContainer):
        from datetime import timedelta
        repo = repo_container.stats
        repo.record_event("u1", "VISIT")
        earlier = datetime.utcnow() - timedelta(seconds=5)

        count = repo.count_events("u1", "VISIT", since=earlier)
        assert count == 1

        later = datetime.utcnow() + timedelta(seconds=5)
        count = repo.count_events("u1", "VISIT", since=later)
        assert count == 0

    def test_delete_by_user(self, repo_container: RepoContainer):
        repo = repo_container.stats
        repo.record_event("u1", "VISIT")
        repo.record_event("u2", "VISIT")

        n = repo.delete_by_user("u1")
        assert n == 1
        assert repo.count(user_id="u1") == 0
        assert repo.count(user_id="u2") == 1

    def test_delete_all(self, repo_container: RepoContainer):
        repo = repo_container.stats
        repo.record_event("u1", "VISIT")
        repo.record_event("u2", "CHAT")

        n = repo.delete_all()
        assert n == 2
        assert repo.count() == 0

    def test_count_with_filters(self, repo_container: RepoContainer):
        repo = repo_container.stats
        repo.record_event("u1", "VISIT", "s1")
        repo.record_event("u1", "CHAT", "s1")

        assert repo.count(user_id="u1", session_id="s1") == 2
        assert repo.count(user_id="u1", event_type="VISIT") == 1
