from typing import Optional, Type
from contextlib import asynccontextmanager

from sqlalchemy import delete, select, update, func

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .abctract import IAsyncCrud, FrozenClassAttributesMeta

from .exceptions import IntegrityConflictException, NotFoundException, RepositoryException
from ._types import SA, DM, CS, PS, PrimitiveValue, FilterValue, IdValue, Filters


class AsyncCrud(IAsyncCrud[SA, DM, CS, PS], metaclass=FrozenClassAttributesMeta):
    sqla_model: Type[SA]
    domain_model: Type[DM]

    @asynccontextmanager
    async def _transaction(self, session: AsyncSession):
        """Context manager for handling transactions with proper rollback on exception"""
        try:
            yield session
            await session.commit()
        except IntegrityError as e:
            await session.rollback()
            raise IntegrityConflictException(
                f"{self.sqla_model.__tablename__} conflicts with existing data: {e}"
            ) from e
        except Exception as e:
            raise RepositoryException(f"Transaction failed: {e}") from e

    async def create(
        self,
        session: AsyncSession,
        data: CS,
    ) -> DM:
        """Create a single entity"""
        try:
            db_model = self.sqla_model(**data.model_dump(exclude_unset=True))
            session.add(db_model)
            await session.commit()
            await session.refresh(db_model)
            return self.domain_model.model_validate(db_model)
        except IntegrityError as e:
            await session.rollback()
            raise IntegrityConflictException(
                f"{self.sqla_model.__tablename__} conflicts with existing data: {e}",
            ) from e
        except Exception as e:
            await session.rollback()
            raise RepositoryException(f"Failed to create {self.sqla_model.__tablename__}: {e}") from e

    async def create_many(
        self,
        session: AsyncSession,
        data: list[DM],
        return_models: bool = False,
    ) -> list[DM] | bool:
        """Create multiple entities at once"""
        db_models = [self.sqla_model(**d.model_dump(exclude_unset=True)) for d in data]

        try:
            async with self._transaction(session):
                session.add_all(db_models)

            if not return_models:
                return True

            for m in db_models:
                await session.refresh(m)

            return [self.domain_model.model_validate(entity) for entity in db_models]
        except Exception as e:
            if not isinstance(e, RepositoryException):
                raise RepositoryException(f"Failed to create multiple {self.sqla_model.__tablename__}: {e}") from e
            raise

    async def get_one(
        self,
        session: AsyncSession,
        id_: IdValue,
        column: str = "id",
    ) -> DM:
        """Get single entity (or raise NotFoundException) by id or other column"""
        try:
            q = select(self.sqla_model).where(getattr(self.sqla_model, column) == id_)
        except AttributeError as e:
            raise RepositoryException(
                f"Column {column} not found on {self.sqla_model.__tablename__}: {e}",
            ) from e

        result = await session.execute(q)
        entity = result.unique().scalar_one_or_none()

        if entity is None:
            raise NotFoundException(f"{self.sqla_model.__tablename__} with {column}={id_} not found")

        return self.domain_model.model_validate(entity)

    async def get_many(
        self,
        session: AsyncSession,
        filter: FilterValue,
        column: str = "id",
        order_by: Optional[str] = None,
        desc: bool = False,
    ) -> list[DM]:
        """Get multiple entities by list of ids"""
        q = select(self.sqla_model)

        try:
            if isinstance(filter, list):
                q = q.where(getattr(self.sqla_model, column).in_(filter))
            elif isinstance(
                filter,
                PrimitiveValue,
            ):
                q = q.where(getattr(self.sqla_model, column) == filter)
        except AttributeError as e:
            raise RepositoryException(
                f"Column {column} not found on {self.sqla_model.__tablename__}: {e}",
            ) from e

        if order_by:
            try:
                order_column = getattr(self.sqla_model, order_by)
                q = q.order_by(order_column.desc() if desc else order_column)
            except AttributeError as e:
                raise RepositoryException(
                    f"Column {order_by} not found on {self.sqla_model.__tablename__}: {e}",
                ) from e

        rows = await session.execute(q)
        return [self.domain_model.model_validate(entity) for entity in rows.unique().scalars().all()]

    async def get_all(
        self,
        session: AsyncSession,
        offset: int = 0,
        limit: Optional[int] = 100,
        order_by: Optional[str] = None,
        desc: bool = False,
    ) -> tuple[list[DM], int]:
        """Get all entities with pagination support and total count"""
        q = select(self.sqla_model)

        if order_by:
            try:
                order_column = getattr(self.sqla_model, order_by)
                q = q.order_by(order_column.desc() if desc else order_column)
            except AttributeError as e:
                raise RepositoryException(
                    f"Column {order_by} not found on {self.sqla_model.__tablename__}: {e}",
                ) from e

        if limit is not None:
            q = q.offset(offset).limit(limit)

        rows = await session.execute(q)

        count_q = select(func.count()).select_from(self.sqla_model)
        count_result = await session.execute(count_q)
        total = count_result.scalar_one()

        return [self.domain_model.model_validate(entity) for entity in rows.unique().scalars().all()], total

    async def patch(
        self,
        session: AsyncSession,
        data: PS,
        id_: IdValue,
        column: str = "id",
    ) -> DM:
        """Patch entity by id and return the updated model"""
        try:
            await self.get_one(session, id_, column)

            q = (
                update(self.sqla_model)
                .where(getattr(self.sqla_model, column) == id_)
                .values(**data.model_dump(exclude_unset=True))
                .returning(self.sqla_model)
            )

            result = await session.execute(q)
            await session.commit()

            updated_entity = result.scalar_one()
            return self.domain_model.model_validate(updated_entity)

        except IntegrityError as e:
            await session.rollback()
            raise IntegrityConflictException(
                f"{self.sqla_model.__tablename__} {column}={id_} conflict with existing data: {e}",
            ) from e
        except Exception as e:
            await session.rollback()
            if not isinstance(e, RepositoryException):
                raise RepositoryException(f"Failed to update {self.sqla_model.__tablename__}: {e}") from e
            raise

    async def update(
        self,
        session: AsyncSession,
        data: DM,
    ) -> DM:
        """Update entity and return the updated model"""
        try:
            await self.get_one(session, data.id)

            q = (
                update(self.sqla_model)
                .where(getattr(self.sqla_model, "id") == data.id)
                .values(**data.model_dump(exclude_unset=True))
                .returning(self.sqla_model)
            )

            result = await session.execute(q)
            await session.commit()

            updated_entity = result.scalar_one()
            return self.domain_model.model_validate(updated_entity)

        except IntegrityError as e:
            await session.rollback()
            raise IntegrityConflictException(
                f"{self.sqla_model.__tablename__} id={data.id} conflict with existing data: {e}",
            ) from e
        except Exception as e:
            await session.rollback()
            if not isinstance(e, RepositoryException):
                raise RepositoryException(f"Failed to update {self.sqla_model.__tablename__}: {e}") from e
            raise

    async def remove(
        self,
        session: AsyncSession,
        id_: IdValue,
        column: str = "id",
        raise_not_found: bool = False,
    ) -> int:
        """Remove entity by id"""
        try:
            query = delete(self.sqla_model).where(getattr(self.sqla_model, column) == id_)
        except AttributeError as e:
            raise RepositoryException(
                f"Column {column} not found on {self.sqla_model.__tablename__}: {e}",
            ) from e

        try:
            result = await session.execute(query)
            await session.commit()

            if result.rowcount == 0 and raise_not_found:
                raise NotFoundException(f"{self.sqla_model.__tablename__} with {column}={id_} not found")

            return result.rowcount
        except Exception as e:
            await session.rollback()
            if not isinstance(e, RepositoryException):
                raise RepositoryException(f"Failed to remove {self.sqla_model.__tablename__}: {e}") from e
            raise

    async def remove_many(
        self,
        session: AsyncSession,
        ids: list[IdValue],
        column: str = "id",
    ) -> int:
        """Remove multiple entities by ids"""
        try:
            query = delete(self.sqla_model).where(getattr(self.sqla_model, column).in_(ids))
        except AttributeError as e:
            raise RepositoryException(
                f"Column {column} not found on {self.sqla_model.__tablename__}: {e}",
            ) from e

        try:
            result = await session.execute(query)
            await session.commit()
            return result.rowcount
        except Exception as e:
            await session.rollback()
            raise RepositoryException(f"Failed to remove multiple {self.sqla_model.__tablename__}: {e}") from e

    async def count(
        self,
        session: AsyncSession,
        filters: Optional[Filters] = None,
    ) -> int:
        """Count entities with optional filtering"""
        q = select(func.count()).select_from(self.sqla_model)

        if filters:
            for column_name, value in filters.items():
                try:
                    q = q.where(getattr(self.sqla_model, column_name) == value)
                except AttributeError as e:
                    raise RepositoryException(
                        f"Column {column_name} not found on {self.sqla_model.__tablename__}: {e}",
                    ) from e

        result = await session.execute(q)
        return result.scalar_one()
