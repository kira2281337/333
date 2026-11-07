import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Link

router = APIRouter(tags=["redirect"])

# Нестандартный код из задания (Laravel «Page Expired»). По HTTP корректнее 410 Gone.
HTTP_419_PAGE_EXPIRED = 419


@router.get("/{code}")
async def follow_link(code: str, db: AsyncSession = Depends(get_db)) -> RedirectResponse:
    try:
        code_uuid = uuid.UUID(code)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Link not found")

    # Атомарно: проверка «активна ли» и инкремент счётчика — один SQL-запрос
    #   UPDATE links SET clicks = clicks + 1 WHERE code = :code AND <активна> RETURNING original_url
    # Нет цикла «прочитал -> прибавил -> записал», поэтому при параллельных запросах
    # нет гонки, и max_clicks нельзя превысить.
    result = await db.execute(
        update(Link)
        .where(Link.code == code_uuid, *Link.active_conditions())
        .values(clicks=Link.clicks + 1)
        .returning(Link.original_url)
        .execution_options(synchronize_session=False)
    )
    original_url = result.scalar_one_or_none()
    if original_url is not None:
        await db.commit()
        return RedirectResponse(original_url, status_code=status.HTTP_302_FOUND)

    # Не обновилось: либо ссылки нет / она удалена (404), либо она просто неактивна (419).
    exists = await db.scalar(select(Link.id).where(Link.code == code_uuid, Link.deleted_at.is_(None)))
    if exists is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Link not found")
    raise HTTPException(HTTP_419_PAGE_EXPIRED, "Link expired")
