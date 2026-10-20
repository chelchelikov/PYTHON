from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import Role


class RegisterIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=100)
    phone: str = Field(pattern=r"^\+?\d{10,15}$", examples=["+79001234567"])
    password: str = Field(min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        if value.isdigit() or value.isalpha():
            raise ValueError("Пароль должен содержать буквы и цифры")
        return value


class LoginIn(BaseModel):
    # При входе формат не проверяется строго: достаточно найти пользователя по адресу
    email: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=1, max_length=72)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    full_name: str
    phone: str
    role: Role
