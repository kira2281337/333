from fastapi import FastAPI

from app.routers import auth, links, redirect

app = FastAPI(title="URL shortener")

app.include_router(auth.router)
app.include_router(links.router)
# Роутер с GET /{code} подключаем последним: это «жадный» маршрут,
# он не должен перехватывать /links, /auth/... и т.д.
app.include_router(redirect.router)
