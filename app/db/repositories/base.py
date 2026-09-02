"""Generic base repository for CRUD database operations."""

from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Generic repository providing standard async database operations."""

    def __init__(self, model: type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    async def get_by_id(self, id: str) -> ModelType | None:
        """Fetch a single record by primary key."""
        result = await self.session.execute(select(self.model).where(self.model.id == id))
        return result.scalars().first()

    async def list_all(self, limit: int = 100, offset: int = 0) -> Sequence[ModelType]:
        """List records with pagination."""
        query = select(self.model).limit(limit).offset(offset)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def create(self, instance: ModelType | None = None, **kwargs: Any) -> ModelType:
        """Instantiate and persist a new model instance, or persist an existing instance."""
        if instance is None:
            instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def delete(self, instance: ModelType) -> None:
        """Delete an instance."""
        await self.session.delete(instance)
        await self.session.flush()
