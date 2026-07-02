"""Shared fixtures for all tests."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session as SASession
from services.database import Base


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh in-memory SQLite DB for each test."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def repo_container(db_session):
    """Create a RepoContainer with a test DB session."""
    from services.repository.container import RepoContainer
    return RepoContainer(db_session)
