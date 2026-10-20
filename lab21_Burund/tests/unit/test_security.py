from datetime import UTC, datetime, timedelta

import jwt
import pytest
from pydantic import ValidationError

from app.core.errors import UnauthorizedError
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.schemas.auth import RegisterIn

SECRET = "unit-secret-key-with-enough-length-1234"


def test_password_hash_and_verify():
    stored = hash_password("secret123")
    assert stored.startswith("pbkdf2$") and "secret123" not in stored
    assert verify_password("secret123", stored)
    assert not verify_password("secret124", stored)
    assert hash_password("secret123") != stored  # у каждого хеша своя соль


@pytest.mark.parametrize("stored", ["", "plain-text", "pbkdf2$abc$def$ghi"])
def test_verify_rejects_malformed_hash(stored):
    assert verify_password("x", stored) is False


def test_token_roundtrip():
    payload = decode_token(create_token(7, "admin", SECRET, 5), SECRET)
    assert payload["sub"] == "7" and payload["role"] == "admin"


def test_expired_and_forged_tokens():
    expired = jwt.encode(
        {"sub": "1", "exp": datetime.now(UTC) - timedelta(minutes=1)}, SECRET, algorithm="HS256"
    )
    with pytest.raises(UnauthorizedError, match="истёк"):
        decode_token(expired, SECRET)
    with pytest.raises(UnauthorizedError):
        decode_token(create_token(1, "user", "another-secret-key-of-enough-length", 5), SECRET)


@pytest.mark.parametrize(
    "password, valid",
    [
        ("abc12345", True),
        ("12345678", False),
        ("abcdefgh", False),
        ("a1", False),
    ],
)
def test_register_password_rules(password, valid):
    data = {"email": "a@b.ru", "full_name": "Тест", "phone": "+79001234567", "password": password}
    if valid:
        RegisterIn(**data)
    else:
        with pytest.raises(ValidationError):
            RegisterIn(**data)
