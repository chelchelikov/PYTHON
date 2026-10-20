from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import current_user, get_auth
from app.models import User
from app.schemas.auth import LoginIn, RegisterIn, TokenOut, UserOut
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Авторизация"])
ERRORS = {401: {"description": "Неверные учётные данные"}}


@router.post(
    "/register",
    response_model=UserOut,
    status_code=201,
    summary="Регистрация клиента",
    responses={409: {"description": "E-mail занят"}},
)
def register(data: RegisterIn, auth: AuthService = Depends(get_auth)):
    return auth.register(data)


@router.post("/login", response_model=TokenOut, summary="Вход (JSON)", responses=ERRORS)
def login(data: LoginIn, auth: AuthService = Depends(get_auth)):
    return TokenOut(access_token=auth.login(data.email, data.password))


@router.post(
    "/token", response_model=TokenOut, summary="Вход (форма OAuth2, для Swagger)", responses=ERRORS
)
def token(form: OAuth2PasswordRequestForm = Depends(), auth: AuthService = Depends(get_auth)):
    return TokenOut(access_token=auth.login(form.username, form.password))


@router.get("/me", response_model=UserOut, summary="Текущий пользователь")
def me(user: User = Depends(current_user)):
    return user
