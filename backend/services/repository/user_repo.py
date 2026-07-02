from services.models.user import User
from .base import BaseRepository


class UserRepository(BaseRepository[User]):
    def get_model(self) -> type[User]:
        return User

    def get_by_username(self, username: str) -> User | None:
        return self.db.query(User).filter(User.username == username).first()

    def get_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

    def get_by_login(self, login: str) -> User | None:
        return self.db.query(User).filter(
            (User.username == login) | (User.email == login)
        ).first()

    def exists(self) -> bool:
        return self.db.query(User).count() > 0

    def list_all(self) -> list[User]:
        return self.db.query(User).order_by(User.created_at.desc()).all()
