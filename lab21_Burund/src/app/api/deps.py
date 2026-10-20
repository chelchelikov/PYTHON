from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.models import User
from app.services.auth_service import AuthService

oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)


def get_session(request: Request):
    yield from request.app.state.db.session()


def get_auth(request: Request, session: Session = Depends(get_session)) -> AuthService:
    settings = request.app.state.settings
    return AuthService(session, settings.jwt_secret, settings.jwt_expire_minutes)


def current_user(
    token: str | None = Depends(oauth2), auth: AuthService = Depends(get_auth)
) -> User:
    return auth.current_user(token)


def admin_user(user: User = Depends(current_user)) -> User:
    return AuthService.require_admin(user)


def get_cache(request: Request):
    return request.app.state.cache
