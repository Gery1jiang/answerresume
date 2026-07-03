"""Tests for ConversationRepository."""

import pytest
from services.repository.container import RepoContainer


class TestConversationRepository:
    def test_count_by_question(self, repo_container: RepoContainer):
        repo = repo_container.conversation
        repo.create(user_id="u1", session_id="s1", role="user", content="What is AI?")
        repo.create(user_id="u1", session_id="s2", role="user", content="What is AI?")
        repo.create(user_id="u1", session_id="s3", role="user", content="How to code?")
        repo.create(user_id="u1", session_id="s4", role="assistant", content="AI is...")

        results = repo.count_by_question(limit=10)
        assert len(results) == 2
        q_map = {q: c for q, c in results}
        assert q_map["What is AI?"] == 2
        assert q_map["How to code?"] == 1

    def test_count_by_question_with_user_filter(self, repo_container: RepoContainer):
        repo = repo_container.conversation
        repo.create(user_id="u1", session_id="s1", role="user", content="Hello")
        repo.create(user_id="u2", session_id="s2", role="user", content="Hello")
        repo.create(user_id="u1", session_id="s3", role="user", content="World")

        results = repo.count_by_question(user_id="u1", limit=10)
        assert len(results) == 2
        q_map = {q: c for q, c in results}
        assert q_map["Hello"] == 1

    def test_list_by_session(self, repo_container: RepoContainer):
        repo = repo_container.conversation
        repo.create(user_id="u1", session_id="s1", role="user", content="Hi")
        repo.create(user_id="u1", session_id="s1", role="assistant", content="Hello!")
        repo.create(user_id="u1", session_id="s2", role="user", content="Other")

        convs = repo.list_by_session("s1")
        assert len(convs) == 2
        assert all(c.session_id == "s1" for c in convs)

    def test_delete_by_user(self, repo_container: RepoContainer):
        repo = repo_container.conversation
        repo.create(user_id="u1", session_id="s1", role="user", content="A")
        repo.create(user_id="u2", session_id="s2", role="user", content="B")

        n = repo.delete_by_user("u1")
        assert n == 1
        assert repo.count(user_id="u1") == 0
        assert repo.count(user_id="u2") == 1

    def test_delete_all(self, repo_container: RepoContainer):
        repo = repo_container.conversation
        repo.create(user_id="u1", session_id="s1", role="user", content="A")
        repo.create(user_id="u2", session_id="s2", role="user", content="B")

        n = repo.delete_all()
        assert n == 2
        assert repo.count() == 0

    def test_count_by_user(self, repo_container: RepoContainer):
        repo = repo_container.conversation
        repo.create(user_id="u1", session_id="s1", role="user", content="A")
        repo.create(user_id="u1", session_id="s2", role="assistant", content="B")
        repo.create(user_id="u2", session_id="s3", role="user", content="C")

        assert repo.count_by_user("u1") == 2
        assert repo.count_by_user("u2") == 1
