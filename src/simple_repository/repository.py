from typing import Generic, Optional, Type
from contextlib import asynccontextmanager

from sqlalchemy import delete, select, update, func

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .exceptions import IntegrityConflictException, NotFoundException, RepositoryException
from .types import SA, DM, CrudMeta, PrimitiveValue, FilterValue, IdValue, Filters
from .protocols import Schema


class AsyncCrud(Generic[SA, DM], metaclass=CrudMeta):
    sqla_model: Type[SA]
    domain_model: Type[DM]

    def __init__(self, sqla_model: Type[SA], domain_model: Type[DM]):
        self.sqla_model = sqla_model
        self.domain_model = domain_model

    @classmethod
    @asynccontextmanager
    async def transaction(cls, session: AsyncSession):
        """Context manager for handling transactions with proper rollback on exception"""
        try:
            yield session
            await session.commit()
        except IntegrityError as e:
            await session.rollback()
            raise IntegrityConflictException(f"{cls.sqla_model.__tablename__} conflicts with existing data: {e}") from e
        except Exception as e:
            raise RepositoryException(f"Transaction failed: {e}") from e

    @classmethod
    async def create(
        cls,
        session: AsyncSession,
        data: DM,
    ) -> DM:
        """Create a single entity"""
        try:
            db_model = cls.sqla_model(**data.model_dump(exclude_unset=True))
            session.add(db_model)
            await session.commit()
            await session.refresh(db_model)
            return cls.domain_model.model_validate(db_model)
        except IntegrityError as e:
            await session.rollback()
            raise IntegrityConflictException(
                f"{cls.sqla_model.__tablename__} conflicts with existing data: {e}",
            ) from e
        except Exception as e:
            await session.rollback()
            raise RepositoryException(f"Failed to create {cls.sqla_model.__tablename__}: {e}") from e

    @classmethod
    async def create_many(
        cls,
        session: AsyncSession,
        data: list[DM],
        return_models: bool = False,
    ) -> list[DM] | bool:
        """Create multiple entities at once"""
        db_models = [cls.sqla_model(**d.model_dump(exclude_unset=True)) for d in data]

        try:
            async with cls.transaction(session):
                session.add_all(db_models)

            if not return_models:
                return True

            for m in db_models:
                await session.refresh(m)

            return [cls.domain_model.model_validate(entity) for entity in db_models]
        except Exception as e:
            if not isinstance(e, RepositoryException):
                raise RepositoryException(f"Failed to create multiple {cls.sqla_model.__tablename__}: {e}") from e
            raise

    @classmethod
    async def get_one(
        cls,
        session: AsyncSession,
        id_: IdValue,
        column: str = "id",
    ) -> DM:
        """Get single entity (or raise NotFoundException) by id or other column"""
        try:
            q = select(cls.sqla_model).where(getattr(cls.sqla_model, column) == id_)
        except AttributeError as e:
            raise RepositoryException(
                f"Column {column} not found on {cls.sqla_model.__tablename__}: {e}",
            ) from e

        result = await session.execute(q)
        entity = result.unique().scalar_one_or_none()

        if entity is None:
            raise NotFoundException(f"{cls.sqla_model.__tablename__} with {column}={id_} not found")

        return cls.domain_model.model_validate(entity)

    @classmethod
    async def get_many(
        cls,
        session: AsyncSession,
        filter: FilterValue,
        column: str = "id",
        order_by: Optional[str] = None,
        desc: bool = False,
    ) -> list[DM]:
        """Get multiple entities by list of ids"""
        q = select(cls.sqla_model)

        try:
            if isinstance(filter, list):
                q = q.where(getattr(cls.sqla_model, column).in_(filter))
            elif isinstance(
                filter,
                PrimitiveValue,
            ):
                q = q.where(getattr(cls.sqla_model, column) == filter)
        except AttributeError as e:
            raise RepositoryException(
                f"Column {column} not found on {cls.sqla_model.__tablename__}: {e}",
            ) from e

        if order_by:
            try:
                order_column = getattr(cls.sqla_model, order_by)
                q = q.order_by(order_column.desc() if desc else order_column)
            except AttributeError as e:
                raise RepositoryException(
                    f"Column {order_by} not found on {cls.sqla_model.__tablename__}: {e}",
                ) from e

        rows = await session.execute(q)
        return [cls.domain_model.model_validate(entity) for entity in rows.unique().scalars().all()]

    @classmethod
    async def get_all(
        cls,
        session: AsyncSession,
        offset: int = 0,
        limit: Optional[int] = 100,
        order_by: Optional[str] = None,
        desc: bool = False,
    ) -> tuple[list[DM], int]:
        """Get all entities with pagination support and total count"""
        q = select(cls.sqla_model)

        if order_by:
            try:
                order_column = getattr(cls.sqla_model, order_by)
                q = q.order_by(order_column.desc() if desc else order_column)
            except AttributeError as e:
                raise RepositoryException(
                    f"Column {order_by} not found on {cls.sqla_model.__tablename__}: {e}",
                ) from e

        if limit is not None:
            q = q.offset(offset).limit(limit)

        rows = await session.execute(q)

        count_q = select(func.count()).select_from(cls.sqla_model)
        count_result = await session.execute(count_q)
        total = count_result.scalar_one()

        return [cls.domain_model.model_validate(entity) for entity in rows.unique().scalars().all()], total

    @classmethod
    async def patch(
        cls,
        session: AsyncSession,
        data: Schema,
        id_: IdValue,
        column: str = "id",
    ) -> DM:
        """Patch entity by id and return the updated model"""
        try:
            await cls.get_one(session, id_, column)

            q = (
                update(cls.sqla_model)
                .where(getattr(cls.sqla_model, column) == id_)
                .values(**data.model_dump(exclude_unset=True))
                .returning(cls.sqla_model)
            )

            result = await session.execute(q)
            await session.commit()

            updated_entity = result.scalar_one()
            return cls.domain_model.model_validate(updated_entity)

        except IntegrityError as e:
            await session.rollback()
            raise IntegrityConflictException(
                f"{cls.sqla_model.__tablename__} {column}={id_} conflict with existing data: {e}",
            ) from e
        except Exception as e:
            await session.rollback()
            if not isinstance(e, RepositoryException):
                raise RepositoryException(f"Failed to update {cls.sqla_model.__tablename__}: {e}") from e
            raise

    @classmethod
    async def update(
        cls,
        session: AsyncSession,
        data: DM,
    ) -> DM:
        """Update entity and return the updated model"""
        try:
            await cls.get_one(session, data.id)

            q = (
                update(cls.sqla_model)
                .where(getattr(cls.sqla_model, "id") == data.id)
                .values(**data.model_dump(exclude_unset=True))
                .returning(cls.sqla_model)
            )

            result = await session.execute(q)
            await session.commit()

            updated_entity = result.scalar_one()
            return cls.domain_model.model_validate(updated_entity)

        except IntegrityError as e:
            await session.rollback()
            raise IntegrityConflictException(
                f"{cls.sqla_model.__tablename__} id={data.id} conflict with existing data: {e}",
            ) from e
        except Exception as e:
            await session.rollback()
            if not isinstance(e, RepositoryException):
                raise RepositoryException(f"Failed to update {cls.sqla_model.__tablename__}: {e}") from e
            raise

    @classmethod
    async def remove(
        cls,
        session: AsyncSession,
        id_: IdValue,
        column: str = "id",
        raise_not_found: bool = False,
    ) -> int:
        """Remove entity by id"""
        try:
            query = delete(cls.sqla_model).where(getattr(cls.sqla_model, column) == id_)
        except AttributeError as e:
            raise RepositoryException(
                f"Column {column} not found on {cls.sqla_model.__tablename__}: {e}",
            ) from e

        try:
            result = await session.execute(query)
            await session.commit()

            if result.rowcount == 0 and raise_not_found:
                raise NotFoundException(f"{cls.sqla_model.__tablename__} with {column}={id_} not found")

            return result.rowcount
        except Exception as e:
            await session.rollback()
            if not isinstance(e, RepositoryException):
                raise RepositoryException(f"Failed to remove {cls.sqla_model.__tablename__}: {e}") from e
            raise

    @classmethod
    async def remove_many(
        cls,
        session: AsyncSession,
        ids: list[IdValue],
        column: str = "id",
    ) -> int:
        """Remove multiple entities by ids"""
        try:
            query = delete(cls.sqla_model).where(getattr(cls.sqla_model, column).in_(ids))
        except AttributeError as e:
            raise RepositoryException(
                f"Column {column} not found on {cls.sqla_model.__tablename__}: {e}",
            ) from e

        try:
            result = await session.execute(query)
            await session.commit()
            return result.rowcount
        except Exception as e:
            await session.rollback()
            raise RepositoryException(f"Failed to remove multiple {cls.sqla_model.__tablename__}: {e}") from e

    @classmethod
    async def count(
        cls,
        session: AsyncSession,
        filters: Optional[Filters] = None,
    ) -> int:
        """Count entities with optional filtering"""
        q = select(func.count()).select_from(cls.sqla_model)

        if filters:
            for column_name, value in filters.items():
                try:
                    q = q.where(getattr(cls.sqla_model, column_name) == value)
                except AttributeError as e:
                    raise RepositoryException(
                        f"Column {column_name} not found on {cls.sqla_model.__tablename__}: {e}",
                    ) from e

        result = await session.execute(q)
        return result.scalar_one()
