from uuid import UUID
from typing import Generic, Sequence, Optional, Type, TypeVar, Union, cast
from contextlib import asynccontextmanager

from sqlalchemy import delete, select, update, func

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .protocols import SqlaModel, DomainModel
from .exceptions import IntegrityConflictException, NotFoundException, RepositoryException, DiffAtrrsOnCreateCrud
from .utils import same_attrs


PrimitiveValue = Union[str, UUID, int, float, bool]

SQLAlchemyModel = TypeVar("SQLAlchemyModel", bound=SqlaModel)
PydanticLike = TypeVar("PydanticLike", bound=DomainModel)


class CrudMeta(type):
    pass


class AsyncCrud(Generic[SQLAlchemyModel, PydanticLike], metaclass=CrudMeta):
    sqla_model: Type[SQLAlchemyModel]
    domain_model: Type[PydanticLike]

    def __init__(self, sqla_model: Type[SQLAlchemyModel], domain_model: Type[PydanticLike]):
        self.sqla_model = sqla_model
        self.domain_model = domain_model

    @classmethod
    @asynccontextmanager
    async def transaction(cls, session: AsyncSession):
        """Context manager for handling transactions with proper rollback on exception"""
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            if isinstance(e, IntegrityError):
                raise IntegrityConflictException(
                    f"{cls.sqla_model.__tablename__} conflicts with existing data: {e}"
                ) from e
            raise RepositoryException(f"Transaction failed: {e}") from e

    @classmethod
    async def create(
        cls,
        session: AsyncSession,
        data: PydanticLike,
    ) -> PydanticLike:
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
        data: list[PydanticLike],
        return_models: bool = False,
    ) -> list[PydanticLike] | bool:
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
        id_: str | UUID | int,
        column: str = "id",
    ) -> PydanticLike:
        """Get single entity by id or other column"""
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
        filter: PrimitiveValue | list[PrimitiveValue],
        column: str = "id",
        order_by: Optional[str] = None,
        desc: bool = False,
    ) -> list[PydanticLike]:
        """Get multiple entities by list of ids"""
        q = select(cls.sqla_model)

        try:
            if isinstance(filter, list):
                q = q.where(getattr(cls.sqla_model, column).in_(filter))
            elif isinstance(
                filter,
                (str, UUID, int, float, bool),
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
    ) -> tuple[Sequence[SQLAlchemyModel], int]:
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

        return [cls.domain_model.model_validate(entity) for entity in rows.unique().scalars().all()], total  # type: ignore

    @classmethod
    async def update(
        cls,
        session: AsyncSession,
        data: PydanticLike,
        id_: str | UUID | int,
        column: str = "id",
    ) -> PydanticLike:
        """Update entity by id and return the updated model"""
        try:
            # First check if entity exists
            await cls.get_one(session, id_, column)

            # Update values using update statement
            q = (
                update(cls.sqla_model)
                .where(getattr(cls.sqla_model, column) == id_)
                .values(**data.model_dump(exclude_unset=True))
                .returning(cls.sqla_model)
            )

            result = await session.execute(q)
            await session.commit()

            # Get the updated entity
            updated_entity = result.scalar_one()
            return cls.domain_model.model_validate(updated_entity)  # type: ignore

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
    async def remove(
        cls,
        session: AsyncSession,
        id_: str | UUID,
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
        ids: list[str | UUID],
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
        filters: dict[str, str] | None = None,
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


def crud_factory(
    sqla_model: Type[SQLAlchemyModel], domain_model: Type[PydanticLike]
) -> Type[AsyncCrud[SQLAlchemyModel, PydanticLike]]:
    "Function for producing flex crud`s"
    if not same_attrs(sqla_model, domain_model):
        raise DiffAtrrsOnCreateCrud()

    new_class_name = f"{sqla_model.__name__}Crud"

    new_cls = CrudMeta(
        new_class_name,
        (AsyncCrud,),
        {
            "sqla_model": sqla_model,
            "domain_model": domain_model,
        },
    )
    return cast(Type[AsyncCrud[SQLAlchemyModel, PydanticLike]], new_cls)
