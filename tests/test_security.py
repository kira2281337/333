import jwt
import pytest

from app.config import settings
from app.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
    verify_password_async,
)


def test_hash_is_argon2id_and_not_plaintext():
    hashed = hash_password("secret-password")
    assert hashed.startswith("$argon2id$")
    assert "secret-password" not in hashed


def test_same_password_gives_different_hashes_due_to_salt():
    assert hash_password("secret-password") != hash_password("secret-password")


def test_verify_password():
    hashed = hash_password("secret-password")
    assert verify_password("secret-password", hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_verify_password_with_garbage_hash_returns_false():
    assert verify_password("anything", "not-a-hash") is False


async def test_verify_password_async_unknown_user_is_false():
    assert await verify_password_async("anything", None) is False


def test_access_token_roundtrip():
    token = create_access_token(42)
    assert decode_access_token(token)["sub"] == "42"


def test_expired_token_is_rejected():
    token = create_access_token(42, expires_minutes=-1)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_token_signed_with_other_key_is_rejected():
    forged = jwt.encode({"sub": "1"}, "other-key", algorithm=settings.jwt_algorithm)
    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(forged)
