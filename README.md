# URL shortener

Сервис сокращения ссылок. Стек: FastAPI (async), PostgreSQL, SQLAlchemy 2.0 (async), Alembic, Pydantic v2,
OAuth2 (password flow, Bearer JWT), argon2id для паролей, pytest.

## Запуск

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

alembic upgrade head                                    # применяет миграции
uvicorn app.main:app --reload                           # http://127.0.0.1:8000/docs
```

## Тесты

```bash
pytest
```

Тесты используют in-memory SQLite (через `aiosqlite`), поэтому Postgres для них не нужен.

## API

| Метод | Путь | Описание |
|-------|------|----------|
| POST | `/auth/register` | Регистрация (`email`, `password` ≥ 8 символов) |
| POST | `/auth/token` | Вход, форма `username` (= email) + `password`, возвращает Bearer-токен |
| GET | `/auth/me` | Текущий пользователь |
| POST | `/links` | Создать ссылку (`original_url`, опц. `expires_at`, `max_clicks`). 201 новая, 200 если у пользователя уже есть активная ссылка на этот URL, 403 при превышении лимита |
| GET | `/links` | Свои ссылки (не удалённые) |
| DELETE | `/links/{id}` | Soft delete своей ссылки (204; чужая или несуществующая — 404) |
| GET | `/{code}` | Публичный редирект: 302 / 419 (истекла или исчерпан лимит кликов) / 404 |

Лимит активных ссылок: `user` — 3, `premium` — 5 (словарь `LINK_LIMITS` в `app/config.py`).
Роль `premium` выставляется напрямую в БД: `UPDATE users SET role = 'premium' WHERE email = '...';`

## Структура

```
app/
  config.py      настройки и LINK_LIMITS
  database.py    async engine, сессия, Base
  models.py      User, Link (+ Link.active_conditions — единое определение «активной» ссылки)
  schemas.py     Pydantic-схемы
  security.py    argon2id, JWT
  deps.py        get_current_user, own_link
  routers/       auth, links, redirect
migrations/      Alembic
tests/           pytest
```
