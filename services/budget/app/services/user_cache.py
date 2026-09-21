from typing import Dict, Any, List, cast
from uuid import UUID

import structlog
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.user_cache import UserProfileModel
from app.services.user_client import get_users_by_ids

logger = structlog.get_logger(__name__)


async def get_users_by_ids_cached(ids: List[str], token: str) -> Dict[str, Dict[str, Any]]:
    """Get users from cache, falling back to HTTP for cache misses."""
    if not ids:
        return {}

    async with AsyncSessionLocal() as session:
        user_uuids = [uid if isinstance(uid, UUID) else UUID(uid) for uid in ids]
        result = await session.execute(
            select(UserProfileModel).where(UserProfileModel.user_id.in_(user_uuids))
        )
        profiles = result.scalars().all()

        cached_map = {
            str(p.user_id): {
                "id": str(p.user_id),
                "email": p.email,
                "first_name": p.first_name,
                "last_name": p.last_name,
                "status": p.status,
                "customer_id": str(p.customer_id) if p.customer_id else None,
                "role": p.role,
            }
            for p in profiles
        }

        cached_ids = {p.user_id for p in profiles}
        missing_ids = [uid for uid in user_uuids if uid not in cached_ids]

        if not missing_ids:
            logger.debug("cache_hit_all_users", count=len(cached_map))
            return cached_map

        logger.warning("cache_miss_partial", missing_count=len(missing_ids), total=len(ids))

        try:
            http_users = await get_users_by_ids([str(uid) for uid in missing_ids], token)

            for user_id, user_data in http_users.items():
                uid = UUID(user_id)
                existing_result = await session.execute(
                    select(UserProfileModel).where(UserProfileModel.user_id == uid)
                )
                existing = existing_result.scalar_one_or_none()

                if existing:
                    existing.email = cast(str, user_data.get("email"))
                    existing.first_name = user_data.get("first_name")
                    existing.last_name = user_data.get("last_name")
                    existing.status = cast(str, user_data.get("status"))
                    existing.customer_id = (
                        UUID(user_data.get("customer_id")) if user_data.get("customer_id") else None
                    )
                    existing.role = cast(str, user_data.get("role"))
                else:
                    profile = UserProfileModel(
                        user_id=uid,
                        email=user_data.get("email"),
                        first_name=user_data.get("first_name"),
                        last_name=user_data.get("last_name"),
                        status=user_data.get("status"),
                        customer_id=(
                            UUID(user_data.get("customer_id"))
                            if user_data.get("customer_id")
                            else None
                        ),
                        role=user_data.get("role"),
                    )
                    session.add(profile)

            await session.commit()
            logger.info("cache_populated_from_http", count=len(http_users))
            cached_map.update(http_users)
        except Exception as e:
            await session.rollback()
            logger.error(
                "batch_fallback_http_failed",
                missing_count=len(missing_ids),
                error=str(e),
            )
            raise

        return cached_map
