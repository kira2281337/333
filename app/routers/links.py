from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import LINK_LIMITS
from app.database import get_db
from app.deps import get_current_user, own_link
from app.models import Link, User, utcnow
from app.schemas import LinkCreate, LinkOut

router = APIRouter(prefix="/links", tags=["links"])


@router.post("", response_model=LinkOut, status_code=status.HTTP_201_CREATED)
async def create_link(
    data: LinkCreate,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Link:
    url = str(data.original_url)

    # 1. Уже есть активная ссылка на тот же URL у этого пользователя — отдаём её (200).
    existing = await db.scalar(
        select(Link).where(
            Link.user_id == user.id,
            Link.original_url == url,
            *Link.active_conditions(),
        )
    )
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return existing

    # 2. Лимит активных ссылок зависит от роли.
    active_count = await db.scalar(
        select(func.count()).select_from(Link).where(Link.user_id == user.id, *Link.active_conditions())
    )
    limit = LINK_LIMITS.get(user.role, LINK_LIMITS["user"])
    if active_count >= limit:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"Active links limit reached ({limit} for role '{user.role}')",
        )

    # 3. Создаём новую; code (uuid4) генерируется на стороне модели.
    link = Link(
        user_id=user.id,
        original_url=url,
        expires_at=data.expires_at,
        max_clicks=data.max_clicks,
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return link


@router.get("", response_model=list[LinkOut])
async def list_links(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Link]:
    """Свои ссылки (не удалённые), включая истёкшие — пользователь видит их статистику."""
    result = await db.scalars(
        select(Link).where(Link.user_id == user.id, Link.deleted_at.is_(None)).order_by(Link.id)
    )
    return list(result)


@router.delete("/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_link(link: Link = Depends(own_link), db: AsyncSession = Depends(get_db)) -> Response:
    """Soft delete: строка остаётся в БД, просто проставляется deleted_at."""
    link.deleted_at = utcnow()
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
