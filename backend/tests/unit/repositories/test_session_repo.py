"""Tests for SessionRepository."""

from services.repository.container import RepoContainer


class TestSessionRepository:
    def test_list_all(self, repo_container: RepoContainer):
        repo = repo_container.session
        repo.create(id="s1", user_id="u1", is_active=True)
        repo.create(id="s2", user_id="u2", is_active=False)

        all_sessions = repo.list_all()
        assert len(all_sessions) == 2

    def test_delete_by_user(self, repo_container: RepoContainer):
        repo = repo_container.session
        repo.create(id="s1", user_id="u1", is_active=True)
        repo.create(id="s2", user_id="u2", is_active=True)

        n = repo.delete_by_user("u1")
        assert n == 1
        assert repo.count(user_id="u1") == 0

    def test_delete_all(self, repo_container: RepoContainer):
        repo = repo_container.session
        repo.create(id="s1", user_id="u1")
        repo.create(id="s2", user_id="u2")

        n = repo.delete_all()
        assert n == 2
        assert repo.count() == 0

    def test_list_active(self, repo_container: RepoContainer):
        repo = repo_container.session
        repo.create(id="s1", user_id="u1", is_active=True)
        repo.create(id="s2", user_id="u1", is_active=False)

        active = repo.list_active("u1")
        assert len(active) == 1
        assert active[0].id == "s1"

    def test_count_active(self, repo_container: RepoContainer):
        repo = repo_container.session
        repo.create(id="s1", user_id="u1", is_active=True)
        repo.create(id="s2", user_id="u1", is_active=False)

        assert repo.count_active("u1") == 1
