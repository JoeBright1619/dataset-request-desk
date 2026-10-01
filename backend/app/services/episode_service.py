"""Read operations for the episode domain."""

from dataclasses import dataclass
from datetime import datetime
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.models.episode import Episode
from app.repositories.episode_repository import EpisodeFilters, EpisodeRepository
from app.schemas.episode import EpisodeListResponse, EpisodeQuality, EpisodeResponse


@dataclass(frozen=True)
class EpisodeListQuery:
    task_name: str | None = None
    quality: str | None = None
    robot_id: str | None = None
    recorded_from: datetime | None = None
    recorded_to: datetime | None = None
    assigned: bool | None = None
    cursor: str | None = None
    limit: int = 50

    def filters(self) -> EpisodeFilters:
        return EpisodeFilters(
            task_name=self.task_name,
            quality=self.quality,
            robot_id=self.robot_id,
            recorded_from=self.recorded_from,
            recorded_to=self.recorded_to,
            assigned=self.assigned,
        )


class EpisodeService:
    def __init__(self, session: AsyncSession) -> None:
        self._episodes = EpisodeRepository(session)

    async def list_episodes(self, query: EpisodeListQuery) -> EpisodeListResponse:
        page = await self._episodes.list(query.filters(), query.cursor, query.limit)
        active_ids = await self._episodes.active_episode_ids(
            [episode.id for episode in page.items]
        )
        return EpisodeListResponse(
            items=[
                self._response(episode, episode.id in active_ids)
                for episode in page.items
            ],
            next_cursor=page.next_cursor,
            prev_cursor=page.prev_cursor,
            has_more=page.has_more,
            has_prev=page.has_prev,
            limit=query.limit,
        )

    async def get_episode(self, episode_id: str) -> EpisodeResponse:
        episode = await self._episodes.get_by_episode_id(episode_id)
        if episode is None:
            raise NotFoundError()
        active_ids = await self._episodes.active_episode_ids([episode.id])
        return self._response(episode, episode.id in active_ids)

    @staticmethod
    def _response(episode: Episode, is_assigned: bool) -> EpisodeResponse:
        return EpisodeResponse(
            id=episode.id,
            episode_id=episode.episode_id,
            robot_id=episode.robot_id,
            task_name=episode.task_name,
            recorded_at=episode.recorded_at,
            duration_seconds=episode.duration_seconds,
            operator_name=episode.operator_name,
            quality=cast(EpisodeQuality, episode.quality),
            is_assigned=is_assigned,
            created_at=episode.created_at,
        )
