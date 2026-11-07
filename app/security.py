from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError
from starlette.concurrency import run_in_threadpool

from app.config import settings

# argon2id — гибрид argon2i и argon2d; соль и параметры хранятся внутри самого хэша.
_hasher = PasswordHasher(type=Type.ID)

# Хэш-заглушка: проверяем его, когда пользователь не найден, чтобы время ответа
# не выдавало, существует ли такой email.
_DUMMY_HASH = _hasher.hash("dummy-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, password)
    except (VerificationError, InvalidHashError):
        return False


# argon2 намеренно «тяжёлый» (CPU + память): в async-приложении его нужно
# выносить в пул потоков, иначе он блокирует event loop.
async def hash_password_async(password: str) -> str:
    return await run_in_threadpool(hash_password, password)


async def verify_password_async(password: str, hashed: str | None) -> bool:
    if hashed is None:
        # Пользователя нет: всё равно тратим то же время на проверку заглушки.
        await run_in_threadpool(verify_password, password, _DUMMY_HASH)
        return False
    return await run_in_threadpool(verify_password, password, hashed)


def create_access_token(user_id: int, expires_minutes: int | None = None) -> str:
    minutes = expires_minutes if expires_minutes is not None else settings.access_token_expire_minutes
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Бросает jwt.PyJWTError, если токен невалиден или просрочен."""
    return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
