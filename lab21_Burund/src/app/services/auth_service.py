import logging

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ForbiddenError, UnauthorizedError
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.models import Role, User
from app.repositories import UserRepository
from app.schemas.auth import RegisterIn

log = logging.getLogger("restaurant.auth")


class AuthService:
    def __init__(self, session: Session, secret: str, expire_minutes: int) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.secret = secret
        self.expire_minutes = expire_minutes

    def register(self, data: RegisterIn, role: Role = Role.USER) -> User:
        if self.users.by_email(data.email):
            raise ConflictError(f"Пользователь {data.email} уже зарегистрирован", "EMAIL_TAKEN")
        user = self.users.add(
            User(
                email=data.email.lower(),
                full_name=data.full_name,
                phone=data.phone,
                password_hash=hash_password(data.password),
                role=role,
            )
        )
        self.session.commit()
        log.info("Зарегистрирован пользователь %s (%s)", user.email, user.role)
        return user

    def login(self, email: str, password: str) -> str:
        user = self.users.by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            raise UnauthorizedError("Неверный e-mail или пароль", "INVALID_CREDENTIALS")
        return create_token(user.id, user.role, self.secret, self.expire_minutes)

    def current_user(self, token: str | None) -> User:
        if not token:
            raise UnauthorizedError("Требуется авторизация", "NOT_AUTHENTICATED")
        payload = decode_token(token, self.secret)
        user = self.users.get(int(payload["sub"]))
        if user is None:
            raise UnauthorizedError("Пользователь не найден", "INVALID_TOKEN")
        return user

    @staticmethod
    def require_admin(user: User) -> User:
        if user.role != Role.ADMIN:
            raise ForbiddenError("Операция доступна только администратору", "ADMIN_ONLY")
        return user

    def ensure_admin(self, email: str, password: str) -> None:
        """Создаёт учётную запись администратора при первом запуске."""
        if self.users.by_email(email) is None:
            self.users.add(
                User(
                    email=email.lower(),
                    full_name="Администратор",
                    phone="+70000000000",
                    password_hash=hash_password(password),
                    role=Role.ADMIN,
                )
            )
            self.session.commit()
